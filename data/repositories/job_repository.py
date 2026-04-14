from __future__ import annotations

from typing import Optional

from data.connection import get_sqlite_connection
from data.models.job_record import JobRecord


class JobRepository:
    def ensure_schema(self) -> None:
        with get_sqlite_connection() as conn:
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    error_code TEXT,
                    error_detail TEXT
                )
                '''
            )
            conn.commit()

    def upsert(self, record: JobRecord) -> None:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            conn.execute(
                '''
                INSERT INTO jobs (
                    job_id, job_type, status, progress, error_code, error_detail
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    job_type=excluded.job_type,
                    status=excluded.status,
                    progress=excluded.progress,
                    error_code=excluded.error_code,
                    error_detail=excluded.error_detail
                '''
                ,
                (
                    record.job_id,
                    record.job_type,
                    record.status,
                    record.progress,
                    record.error_code,
                    record.error_detail,
                ),
            )
            conn.commit()

    def get_by_id(self, job_id: str) -> Optional[JobRecord]:
        self.ensure_schema()
        with get_sqlite_connection() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            return JobRecord(**dict(row))
