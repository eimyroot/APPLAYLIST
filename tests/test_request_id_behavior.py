from fastapi.testclient import TestClient

from api.main import app


def test_health_response_contains_request_id_header() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_health_preserves_supplied_request_id() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"X-Request-ID": "bundle-13-test-id"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "bundle-13-test-id"
