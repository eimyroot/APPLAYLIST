from __future__ import annotations

from core.analysis.job_contract import AnalysisJobCounts, AnalysisJobSnapshot
from data.repositories.analysis_job_repository import AnalysisJobRepository


class AnalysisJobService:
    def __init__(self, repository: AnalysisJobRepository | None = None) -> None:
        self._repo = repository or AnalysisJobRepository()

    def create_job(
        self,
        *,
        selected: int,
        preferred_provider: str | None = None,
    ) -> AnalysisJobSnapshot:
        if selected <= 0:
            raise ValueError("analysis job scope must contain at least one track")
        return self._repo.create(
            selected=selected,
            preferred_provider=preferred_provider,
        )

    def get_job(self, job_id: str) -> AnalysisJobSnapshot | None:
        return self._repo.get(job_id)

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

    def record_success(self, job_id: str, *, uncertain: bool = False) -> AnalysisJobSnapshot:
        current = self._require_running(job_id)
        counts = AnalysisJobCounts(
            selected=current.counts.selected,
            completed=current.counts.completed + 1,
            succeeded=current.counts.succeeded + 1,
            failed=current.counts.failed,
            uncertain=current.counts.uncertain + int(bool(uncertain)),
        )
        return self._repo.update(
            job_id,
            status=current.status,
            counts=counts,
            cancel_requested=current.cancel_requested,
            error_code=current.error_code,
            error_detail=current.error_detail,
        )

    def record_failure(self, job_id: str) -> AnalysisJobSnapshot:
        current = self._require_running(job_id)
        counts = AnalysisJobCounts(
            selected=current.counts.selected,
            completed=current.counts.completed + 1,
            succeeded=current.counts.succeeded,
            failed=current.counts.failed + 1,
            uncertain=current.counts.uncertain,
        )
        return self._repo.update(
            job_id,
            status=current.status,
            counts=counts,
            cancel_requested=current.cancel_requested,
            error_code=current.error_code,
            error_detail=current.error_detail,
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

    def _require_running(self, job_id: str) -> AnalysisJobSnapshot:
        current = self._require(job_id)
        if current.status not in {"running", "cancelling"}:
            raise ValueError("analysis result can only be recorded for an active job")
        if current.counts.completed >= current.counts.selected:
            raise ValueError("analysis job selected scope is already complete")
        return current
