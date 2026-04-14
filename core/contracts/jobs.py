from pydantic import BaseModel
from typing import Optional


class JobStatus(BaseModel):
    job_id: str
    job_type: str
    status: str
    progress: float = 0.0
    error_code: Optional[str] = None
    error_detail: Optional[str] = None
