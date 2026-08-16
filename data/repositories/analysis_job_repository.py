from __future__ import annotations

from uuid import uuid4

from core.analysis.job_contract import AnalysisJobCounts, AnalysisJobSnapshot
from data.connection import get_sqlite_connection
from data.models.analysis_job_record import AnalysisJobRecord


class AnalysisJobRepository:
    def ensure_schema(self) -> None:
        with get_sqlite_connection() as conn:
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS analysis_jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    preferred_provider TEXT,
                    selected INTEGER NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    succeeded INTEGER NOT NULL DEFAULT 0,
                    failed INTEGER NOT NULL DEFAULT 0,
                    uncertain INTEGER NOT NULL DEFAULT 0,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    error_code TEXT,
                    error_detail TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CHECK (selected >= 0),
                    CHECK (completed >= 0),
                    CHECK (succeeded >= 0),
                    CHECK (failed >= 0),
                    CHECK (uncertain >= 0),
                    CHECK (completed = succeeded + failed),
                    CHECK (completed <= selected),
                    CHECK (uncertain <= succeeded),
                    CHECK (cancel_requested IN (0, 1))
                )
                '''
            )
            conn.commit()

    def create(
        self,
        *,
        selected: int,
        preferred_provider: str | None = None,
        job_id: str | None = None,
    ) -> AnalysisJobSnapshot:
        counts = AnalysisJobCounts(selected=selected)
        normalized_job_id = job_id or f"aj_{uuid4().hex}"
        record = AnalysisJobRecord(
            job_id=normalized_job_id,
            status="pending",
            preferred_provider=self._normalize_provider(preferred_provider),
            selected=counts.selected,
        )
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            conn.execute(
                '''
                INSERT INTO analysis_jobs (
                    job_id, status, preferred_provider, selected, completed,
                    succeeded, failed, uncertain, cancel_requested,
                    error_code, error_detail
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    record.job_id,
                    record.status,
                    record.preferred_provider,
                    record.selected,
                    record.completed,
                    record.succeeded,
                    record.failed,
                    record.uncertain,
                    int(record.cancel_requested),
                    record.error_code,
                    record.error_detail,
                ),
            )
            conn.commit()
        snapshot = self.get(normalized_job_id)
        if snapshot is None:
            raise RuntimeError("analysis job insert was not observable")
        return snapshot

    def get(self, job_id: str) -> AnalysisJobSnapshot | None:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            row = conn.execute(
                "SELECT * FROM analysis_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return self._snapshot_from_row(dict(row))

    def update(
        self,
        job_id: str,
        *,
        status: str,
        counts: AnalysisJobCounts,
        cancel_requested: bool | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> AnalysisJobSnapshot:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM analysis_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise KeyError("unknown analysis job")
            current = self._snapshot_from_row(dict(row))
            if counts.has_regressed_from(current.counts):
                raise ValueError("analysis job counts must be monotonic")
            next_cancel_requested = (
                current.cancel_requested
                if cancel_requested is None
                else bool(cancel_requested)
            )
            candidate = AnalysisJobSnapshot(
                job_id=job_id,
                status=status,  # type: ignore[arg-type]
                counts=counts,
                preferred_provider=current.preferred_provider,
                cancel_requested=next_cancel_requested,
                error_code=error_code,
                error_detail=error_detail,
            )
            conn.execute(
                '''
                UPDATE analysis_jobs
                SET status = ?, completed = ?, succeeded = ?, failed = ?,
                    uncertain = ?, cancel_requested = ?, error_code = ?,
                    error_detail = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
                ''',
                (
                    candidate.status,
                    candidate.counts.completed,
                    candidate.counts.succeeded,
                    candidate.counts.failed,
                    candidate.counts.uncertain,
                    int(candidate.cancel_requested),
                    candidate.error_code,
                    candidate.error_detail,
                    job_id,
                ),
            )
            conn.commit()
        return candidate

    def request_cancel(self, job_id: str) -> AnalysisJobSnapshot:
        current = self.get(job_id)
        if current is None:
            raise KeyError("unknown analysis job")
        if current.status in {"done", "failed", "cancelled"}:
            return current
        return self.update(
            job_id,
            status="cancelling",
            counts=current.counts,
            cancel_requested=True,
            error_code=current.error_code,
            error_detail=current.error_detail,
        )

    @staticmethod
    def _normalize_provider(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    @staticmethod
    def _snapshot_from_row(row: dict[str, object]) -> AnalysisJobSnapshot:
        return AnalysisJobSnapshot(
            job_id=str(row["job_id"]),
            status=str(row["status"]),  # type: ignore[arg-type]
            counts=AnalysisJobCounts(
                selected=int(row["selected"]),
                completed=int(row["completed"]),
                succeeded=int(row["succeeded"]),
                failed=int(row["failed"]),
                uncertain=int(row["uncertain"]),
            ),
            preferred_provider=(
                str(row["preferred_provider"])
                if row["preferred_provider"] is not None
                else None
            ),
            cancel_requested=bool(row["cancel_requested"]),
            error_code=(str(row["error_code"]) if row["error_code"] is not None else None),
            error_detail=(
                str(row["error_detail"])
                if row["error_detail"] is not None
                else None
            ),
        )
