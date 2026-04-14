from fastapi.testclient import TestClient

from api.main import app
from services.jobs.queue import job_queue
from workers.base_worker import BaseWorker


def test_create_and_get_job() -> None:
    job_queue.clear()
    client = TestClient(app)

    response = client.post("/jobs/analyze")
    assert response.status_code == 200
    payload = response.json()

    job_id = payload["job_id"]
    assert payload["job_type"] == "analyze"
    assert payload["status"] == "pending"

    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    fetched = response.json()
    assert fetched["job_id"] == job_id
    assert fetched["status"] == "pending"


def test_worker_processes_job() -> None:
    job_queue.clear()
    client = TestClient(app)
    worker = BaseWorker()

    response = client.post("/jobs/scan")
    job_id = response.json()["job_id"]

    processed = worker.process_next()
    assert processed is not None
    assert processed["job_id"] == job_id

    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    fetched = response.json()
    assert fetched["status"] == "done"
    assert fetched["progress"] == 1.0
