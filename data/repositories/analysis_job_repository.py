from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from core.analysis.job_contract import AnalysisJobCounts, AnalysisJobSnapshot
from data.connection import get_sqlite_connection
from data.models.analysis_job_record import AnalysisJobRecord

MAX_ANALYSIS_JOB_TRACKS = 10_000


class AnalysisJobRepository:
    def ensure_schema(self) -> None:
        with get_sqlite_connection() as conn:
            conn.executescript(
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
                    CHECK (selected > 0),
                    CHECK (completed >= 0),
                    CHECK (succeeded >= 0),
                    CHECK (failed >= 0),
                    CHECK (uncertain >= 0),
                    CHECK (completed = succeeded + failed),
                    CHECK (completed <= selected),
                    CHECK (uncertain <= succeeded),
                    CHECK (cancel_requested IN (0, 1))
                );

                CREATE TABLE IF NOT EXISTS analysis_job_targets (
                    job_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    track_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'succeeded', 'failed')),
                    evidence_id TEXT,
                    error_code TEXT,
                    PRIMARY KEY (job_id, ordinal),
                    UNIQUE (job_id, track_id),
                    FOREIGN KEY (job_id) REFERENCES analysis_jobs(job_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_analysis_job_targets_job_status
                    ON analysis_job_targets(job_id, status, ordinal);
                '''
            )
            conn.commit()

    def create_scope(
        self,
        *,
        track_ids: Sequence[str],
        preferred_provider: str | None = None,
        job_id: str | None = None,
    ) -> AnalysisJobSnapshot:
        normalized_track_ids = self._normalize_track_ids(track_ids)
        counts = AnalysisJobCounts(selected=len(normalized_track_ids))
        normalized_job_id = job_id or f"aj_{uuid4().hex}"
        record = AnalysisJobRecord(
            job_id=normalized_job_id,
            status="pending",
            preferred_provider=self._normalize_provider(preferred_provider),
            selected=counts.selected,
        )
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
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
            conn.executemany(
                '''
                INSERT INTO analysis_job_targets (job_id, ordinal, track_id)
                VALUES (?, ?, ?)
                ''',
                (
                    (normalized_job_id, ordinal, track_id)
                    for ordinal, track_id in enumerate(normalized_track_ids)
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

    def get_targets(self, job_id: str) -> tuple[str, ...]:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            job = conn.execute(
                "SELECT selected FROM analysis_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if job is None:
                raise KeyError("unknown analysis job")
            rows = conn.execute(
                '''
                SELECT track_id
                FROM analysis_job_targets
                WHERE job_id = ?
                ORDER BY ordinal
                ''',
                (job_id,),
            ).fetchall()
        targets = tuple(str(row["track_id"]) for row in rows)
        if len(targets) != int(job["selected"]):
            raise RuntimeError("analysis job target scope is inconsistent")
        return targets

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
            self._write_snapshot(conn, candidate)
            conn.commit()
        return candidate

    def record_target_outcome(
        self,
        job_id: str,
        *,
        track_id: str,
        status: str,
        evidence_id: str,
        uncertain: bool = False,
        error_code: str | None = None,
    ) -> AnalysisJobSnapshot:
        if status not in {"succeeded", "failed"}:
            raise ValueError("target outcome must be succeeded or failed")
        if status == "failed" and uncertain:
            raise ValueError("failed target cannot be marked uncertain")
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise ValueError("target outcome requires an evidence_id")

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
            if current.status not in {"running", "cancelling"}:
                raise ValueError("analysis target outcome requires an active job")
            if current.counts.completed >= current.counts.selected:
                raise ValueError("analysis job selected scope is already complete")

            target = conn.execute(
                '''
                SELECT status
                FROM analysis_job_targets
                WHERE job_id = ? AND track_id = ?
                ''',
                (job_id, track_id),
            ).fetchone()
            if target is None:
                raise KeyError("track is outside analysis job scope")
            if str(target["status"]) != "pending":
                raise ValueError("analysis target outcome is already recorded")

            succeeded = current.counts.succeeded + int(status == "succeeded")
            failed = current.counts.failed + int(status == "failed")
            counts = AnalysisJobCounts(
                selected=current.counts.selected,
                completed=current.counts.completed + 1,
                succeeded=succeeded,
                failed=failed,
                uncertain=current.counts.uncertain + int(bool(uncertain)),
            )
            candidate = AnalysisJobSnapshot(
                job_id=job_id,
                status=current.status,
                counts=counts,
                preferred_provider=current.preferred_provider,
                cancel_requested=current.cancel_requested,
                error_code=current.error_code,
                error_detail=current.error_detail,
            )
            conn.execute(
                '''
                UPDATE analysis_job_targets
                SET status = ?, evidence_id = ?, error_code = ?
                WHERE job_id = ? AND track_id = ? AND status = 'pending'
                ''',
                (
                    status,
                    evidence_id.strip(),
                    error_code,
                    job_id,
                    track_id,
                ),
            )
            self._write_snapshot(conn, candidate)
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
    def _write_snapshot(conn: object, snapshot: AnalysisJobSnapshot) -> None:
        conn.execute(  # type: ignore[attr-defined]
            '''
            UPDATE analysis_jobs
            SET status = ?, completed = ?, succeeded = ?, failed = ?,
                uncertain = ?, cancel_requested = ?, error_code = ?,
                error_detail = ?, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
            ''',
            (
                snapshot.status,
                snapshot.counts.completed,
                snapshot.counts.succeeded,
                snapshot.counts.failed,
                snapshot.counts.uncertain,
                int(snapshot.cancel_requested),
                snapshot.error_code,
                snapshot.error_detail,
                snapshot.job_id,
            ),
        )

    @staticmethod
    def _normalize_track_ids(track_ids: Sequence[str]) -> tuple[str, ...]:
        if isinstance(track_ids, (str, bytes)):
            raise TypeError("analysis track scope must be a sequence of track IDs")
        normalized: list[str] = []
        seen: set[str] = set()
        for value in track_ids:
            if not isinstance(value, str):
                raise TypeError("analysis track IDs must be text")
            track_id = value.strip()
            if not track_id:
                raise ValueError("analysis track IDs must be non-empty")
            if len(track_id) > 256:
                raise ValueError("analysis track ID is too long")
            if track_id in seen:
                raise ValueError("analysis track scope contains duplicate track IDs")
            seen.add(track_id)
            normalized.append(track_id)
        if not normalized:
            raise ValueError("analysis job scope must contain at least one track")
        if len(normalized) > MAX_ANALYSIS_JOB_TRACKS:
            raise ValueError("analysis job scope exceeds the bounded track limit")
        return tuple(normalized)

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
