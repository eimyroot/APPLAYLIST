from pathlib import Path

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

def test_pipeline_run_initializes_fresh_database_schema(monkeypatch, tmp_path) -> None:
    from core.config.settings import get_settings

    database_path = tmp_path / "fresh-pipeline.db"
    audio_path = tmp_path / "audio"
    artifacts_path = tmp_path / "artifacts"
    exports_path = tmp_path / "exports"
    logs_path = tmp_path / "logs"
    audio_path.mkdir()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("ARTIFACTS_DIR", str(artifacts_path))
    monkeypatch.setenv("EXPORTS_DIR", str(exports_path))
    monkeypatch.setenv("LOGS_DIR", str(logs_path))
    get_settings.cache_clear()

    try:
        response = TestClient(app).post(
            "/pipeline/run",
            json={"path": str(audio_path), "limit": 3},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["result"]["tracks"] == []

    export = payload["result"]["export"]
    exported_paths = [
        Path(value)
        for key, value in export.items()
        if key.endswith("_path") and isinstance(value, str)
    ]

    assert exported_paths
    assert all(path.exists() for path in exported_paths)
