from __future__ import annotations

from core.analysis.execution_identity import (
    AnalysisExecutionIdentity,
    is_content_addressed_track_id,
)
from core.analysis.provider_contract import ProviderContractError
from core.analysis.provider_service import RoutedAnalysisService
from core.analysis.job_contract import AnalysisJobSnapshot
from data.repositories.track_repository import TrackRepository
from services.analysis.job_service import AnalysisJobService
from services.analysis.result_store import AnalysisResultStore


class AnalysisBatchRunner:
    def __init__(
        self,
        *,
        analysis_service: RoutedAnalysisService | None = None,
        job_service: AnalysisJobService | None = None,
        result_store: AnalysisResultStore | None = None,
        track_repository: TrackRepository | None = None,
    ) -> None:
        self._analysis = analysis_service or RoutedAnalysisService()
        self._jobs = job_service or AnalysisJobService()
        self._results = result_store or AnalysisResultStore()
        self._tracks = track_repository or TrackRepository()

    def run(self, job_id: str) -> AnalysisJobSnapshot:
        job = self._jobs.get_job(job_id)
        if job is None:
            raise KeyError("unknown analysis job")
        if job.cancel_requested or job.status == "cancelling":
            return self._jobs.finish(job_id)
        if job.status != "pending":
            raise ValueError("analysis batch runner requires a pending job")

        targets = self._jobs.get_targets(job_id)
        execution_identity = self._safe_execution_identity(job.preferred_provider)
        self._jobs.mark_running(job_id)

        try:
            for track_id in targets:
                current = self._jobs.get_job(job_id)
                if current is None:
                    raise RuntimeError("analysis job disappeared during execution")
                if current.cancel_requested or current.status == "cancelling":
                    break

                track = self._tracks.get_by_id(track_id)
                if track is None or not isinstance(track.path, str) or not track.path.strip():
                    error = LookupError("track unavailable")
                    evidence = self._results.persist_failure(
                        track_id=track_id,
                        preferred_provider=current.preferred_provider,
                        error=error,
                    )
                    self._jobs.record_failure(
                        job_id,
                        track_id=track_id,
                        evidence_id=evidence.evidence_id,
                        error_code=evidence.error_code or "track_unavailable",
                    )
                    continue

                if execution_identity is not None and is_content_addressed_track_id(track_id):
                    reusable = self._results.reusable_success(
                        track_id=track_id,
                        execution_identity=execution_identity,
                    )
                    if reusable is not None:
                        self._jobs.record_success(
                            job_id,
                            track_id=track_id,
                            evidence_id=reusable.evidence_id,
                            uncertain=self._results.is_uncertain_evidence(reusable),
                        )
                        continue

                try:
                    result = self._analysis.analyze_path(
                        track.path,
                        preferred_provider=current.preferred_provider,
                    )
                except ProviderContractError as error:
                    evidence = self._results.persist_failure(
                        track_id=track_id,
                        preferred_provider=current.preferred_provider,
                        error=error,
                    )
                    self._jobs.record_failure(
                        job_id,
                        track_id=track_id,
                        evidence_id=evidence.evidence_id,
                        error_code=evidence.error_code or "provider_error",
                    )
                    continue
                except Exception as error:
                    evidence = self._results.persist_failure(
                        track_id=track_id,
                        preferred_provider=current.preferred_provider,
                        error=error,
                    )
                    self._jobs.record_failure(
                        job_id,
                        track_id=track_id,
                        evidence_id=evidence.evidence_id,
                        error_code=evidence.error_code or "analysis_internal_error",
                    )
                    continue

                evidence = self._results.persist_success(track_id=track_id, result=result)
                self._jobs.record_success(
                    job_id,
                    track_id=track_id,
                    evidence_id=evidence.evidence_id,
                    uncertain=self._results.is_uncertain(result),
                )
        except Exception:
            current = self._jobs.get_job(job_id)
            if current is not None and current.status not in {"done", "failed", "cancelled"}:
                return self._jobs.fail_job(
                    job_id,
                    error_code="analysis_job_integrity_error",
                    error_detail="Analysis job stopped because its persisted evidence could not be updated safely.",
                )
            raise

        return self._jobs.finish(job_id)

    def _safe_execution_identity(
        self,
        preferred_provider: str | None,
    ) -> AnalysisExecutionIdentity | None:
        """Probe optional reuse identity without changing analysis correctness semantics."""

        resolver = getattr(self._analysis, "execution_identity", None)
        if not callable(resolver):
            return None
        try:
            identity = resolver(preferred_provider=preferred_provider)
        except Exception:
            return None
        return identity if isinstance(identity, AnalysisExecutionIdentity) else None
