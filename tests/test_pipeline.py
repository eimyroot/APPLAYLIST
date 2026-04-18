from fastapi.testclient import TestClient

from api.main import app


def test_pipeline_run() -> None:
    client = TestClient(app)

    response = client.post(
        "/pipeline/run",
        json={
            "path": "/tmp",
            "limit": 3,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert "result" in data
    assert "tracks" in data["result"]
    assert "export" in data["result"]
