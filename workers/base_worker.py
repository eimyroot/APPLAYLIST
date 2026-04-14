from __future__ import annotations

from services.jobs.manager import JobManager
from services.jobs.queue import job_queue


class BaseWorker:
    def __init__(self) -> None:
        self.manager = JobManager()

    def process_next(self) -> dict | None:
        payload = job_queue.dequeue()
        if payload is None:
            return None

        job_id = payload["job_id"]
        self.manager.mark_running(job_id, progress=0.25)

        # placeholder for real worker logic
        self.manager.mark_done(job_id)

        return payload
