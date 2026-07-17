from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.jobs.manager import JobManager


def create_jobs_router(manager: JobManager | None = None) -> APIRouter:
    router = APIRouter(prefix="/jobs", tags=["jobs"])
    job_manager = manager or JobManager()

    @router.post("/{job_type}")
    def create_job(job_type: str) -> dict:
        job = job_manager.create_job(job_type=job_type)
        return job.model_dump()

    @router.get("/{job_id}")
    def get_job(job_id: str) -> dict:
        job = job_manager.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job.model_dump()

    return router


# Backward-compatible export. Application construction uses create_jobs_router().
router = create_jobs_router()
