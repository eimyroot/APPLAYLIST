import os

from fastapi.testclient import TestClient

from api.main import create_app
from api.security.settings import SecuritySettings


def _clear_auth_env() -> None:
    os.environ.pop("AUTH_ENABLED", None)
    os.environ.pop("API_KEY", None)
    os.environ.pop("API_KEY_HEADER_NAME", None)
    os.environ.pop("APP_ENV", None)


def test_auth_failure_includes_request_id_in_body_and_header() -> None:
    try:
        os.environ["AUTH_ENABLED"] = "true"
        os.environ["API_KEY"] = "bundle14-secret"

        app = create_app(SecuritySettings())
        client = TestClient(app)

        response = client.post("/pipeline/run", json={"path": "/tmp", "limit": 1})

        assert response.status_code == 401
        body = response.json()
        rid_body = body["error"]["request_id"]
        rid_header = response.headers.get("X-Request-ID")

        assert rid_body
        assert rid_header
        assert rid_body == rid_header
    finally:
        _clear_auth_env()
