from __future__ import annotations

from collections.abc import Sequence

from core.analysis.job_contract import AnalysisJobSnapshot
from data.repositories.analysis_job_repository import AnalysisJobRepository


class AnalysisJobService:
    def __init__(self, repository: AnalysisJobRepository | None = None) -> None:
        self._repo = repository or AnalysisJobRepository()

    def create_job(
        self,
        *,
        track_ids: Sequence[str],
        preferred_provider: str | None = None,
    ) -> AnalysisJobSnapshot:
        return self._repo.create_scope(
            track_ids=track_ids,
            preferred_provider=preferred_provider,
        )

    def get_job(self, job_id: str) -> AnalysisJobSnapshot | None:
        return self._repo.get(job_id)

    def get_targets(self, job_id: str) -> tuple[str, ...]:
        return self._repo.get_targets(job_id)

    def mark_running(self, job_id: str) -> AnalysisJobSnapshot:
        current = self._require(job_id)
        if current.status not in {"pending", "running"}:
            raise ValueError("analysis job cannot enter running state")
        return self._repo.update(
            job_id,
            status="running",
            counts=current.counts,
            cancel_requested=current.cancel_requested,
            error_code=current.error_code,
            error_detail=current.error_detail,
        )

    def record_success(
        self,
        job_id: str,
        *,
        track_id: str,
        evidence_id: str,
        uncertain: bool = False,
    ) -> AnalysisJobSnapshot:
        return self._repo.record_target_outcome(
            job_id,
            track_id=track_id,
            status="succeeded",
            evidence_id=evidence_id,
            uncertain=uncertain,
        )

    def record_failure(
        self,
        job_id: str,
        *,
        track_id: str,
        evidence_id: str,
        error_code: str,
    ) -> AnalysisJobSnapshot:
        return self._repo.record_target_outcome(
            job_id,
            track_id=track_id,
            status="failed",
            evidence_id=evidence_id,
            error_code=error_code,
        )

    def request_cancel(self, job_id: str) -> AnalysisJobSnapshot:
        return self._repo.request_cancel(job_id)

    def finish(self, job_id: str) -> AnalysisJobSnapshot:
        current = self._require(job_id)
        if current.status == "cancelled":
            return current
        if current.cancel_requested or current.status == "cancelling":
            return self._repo.update(
                job_id,
                status="cancelled",
                counts=current.counts,
                cancel_requested=True,
                error_code=current.error_code,
                error_detail=current.error_detail,
            )
        if current.status != "running":
            raise ValueError("only running analysis jobs can finish")
        if current.counts.completed != current.counts.selected:
            raise ValueError("analysis job cannot finish before selected scope completes")
        return self._repo.update(
            job_id,
            status="done",
            counts=current.counts,
            cancel_requested=False,
        )

    def fail_job(
        self,
        job_id: str,
        *,
        error_code: str,
        error_detail: str,
    ) -> AnalysisJobSnapshot:
        current = self._require(job_id)
        if current.status in {"done", "failed", "cancelled"}:
            raise ValueError("terminal analysis job state is immutable")
        return self._repo.update(
            job_id,
            status="failed",
            counts=current.counts,
            cancel_requested=current.cancel_requested,
            error_code=error_code.strip()[:128] or "analysis_job_failed",
            error_detail=error_detail.strip()[:512] or "analysis job failed",
        )

    def _require(self, job_id: str) -> AnalysisJobSnapshot:
        current = self._repo.get(job_id)
        if current is None:
            raise KeyError("unknown analysis job")
        return current
