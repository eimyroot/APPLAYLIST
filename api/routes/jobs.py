from fastapi import APIRouter, HTTPException

from services.jobs.manager import JobManager

router = APIRouter(prefix="/jobs", tags=["jobs"])
manager = JobManager()


@router.post("/{job_type}")
def create_job(job_type: str) -> dict:
    job = manager.create_job(job_type=job_type)
    return job.model_dump()


@router.get("/{job_id}")
def get_job(job_id: str) -> dict:
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump()
