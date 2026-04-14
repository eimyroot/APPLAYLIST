from dataclasses import dataclass
from typing import Optional


@dataclass
class JobRecord:
    job_id: str
    job_type: str
    status: str
    progress: float = 0.0
    error_code: Optional[str] = None
    error_detail: Optional[str] = None
