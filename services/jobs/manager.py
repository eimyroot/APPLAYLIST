from __future__ import annotations

from uuid import uuid4

from core.contracts.jobs import JobStatus
from data.models.job_record import JobRecord
from data.repositories.job_repository import JobRepository
from services.jobs.queue import job_queue


class JobManager:
    def __init__(self) -> None:
        self.repo = JobRepository()

    def create_job(self, job_type: str) -> JobStatus:
        job_id = str(uuid4())
        record = JobRecord(
            job_id=job_id,
            job_type=job_type,
            status="pending",
            progress=0.0,
        )
        self.repo.upsert(record)
        job_queue.enqueue({"job_id": job_id, "job_type": job_type})
        return JobStatus(
            job_id=job_id,
            job_type=job_type,
            status="pending",
            progress=0.0,
        )

    def get_job(self, job_id: str) -> JobStatus | None:
        record = self.repo.get_by_id(job_id)
        if record is None:
            return None
        return JobStatus(
            job_id=record.job_id,
            job_type=record.job_type,
            status=record.status,
            progress=record.progress,
            error_code=record.error_code,
            error_detail=record.error_detail,
        )

    def mark_running(self, job_id: str, progress: float = 0.0) -> JobStatus | None:
        record = self.repo.get_by_id(job_id)
        if record is None:
            return None
        record.status = "running"
        record.progress = progress
        self.repo.upsert(record)
        return self.get_job(job_id)

    def mark_done(self, job_id: str) -> JobStatus | None:
        record = self.repo.get_by_id(job_id)
        if record is None:
            return None
        record.status = "done"
        record.progress = 1.0
        self.repo.upsert(record)
        return self.get_job(job_id)

    def mark_failed(self, job_id: str, error_code: str, error_detail: str) -> JobStatus | None:
        record = self.repo.get_by_id(job_id)
        if record is None:
            return None
        record.status = "failed"
        record.error_code = error_code
        record.error_detail = error_detail
        self.repo.upsert(record)
        return self.get_job(job_id)
