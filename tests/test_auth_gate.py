import os

from fastapi.testclient import TestClient

from api.main import create_app
from api.security.settings import SecuritySettings


def _build_app():
    return create_app(SecuritySettings())


def _set_auth_env(enabled: bool, api_key: str, *, app_env: str = "development") -> None:
    os.environ["APP_ENV"] = app_env
    os.environ["AUTH_ENABLED"] = "true" if enabled else "false"
    os.environ["API_KEY"] = api_key
    if app_env.lower() in {"prod", "production"}:
        os.environ["ALLOW_ORIGINS"] = "https://app.example.test"
    else:
        os.environ.pop("ALLOW_ORIGINS", None)


def _clear_auth_env() -> None:
    os.environ.pop("AUTH_ENABLED", None)
    os.environ.pop("API_KEY", None)
    os.environ.pop("API_KEY_HEADER_NAME", None)
    os.environ.pop("APP_ENV", None)
    os.environ.pop("ALLOW_ORIGINS", None)


def test_write_endpoint_rejects_missing_api_key_when_auth_enabled() -> None:
    try:
        _set_auth_env(True, "secret-test-key")
        client = TestClient(_build_app())

        response = client.post("/pipeline/run", json={"path": "/tmp", "limit": 1})
        assert response.status_code == 401
        body = response.json()
        assert body["error"]["type"] == "unauthorized"
    finally:
        _clear_auth_env()


def test_write_endpoint_accepts_valid_api_key_when_auth_enabled() -> None:
    try:
        _set_auth_env(True, "secret-test-key")
        client = TestClient(_build_app())

        response = client.post(
            "/pipeline/run",
            json={"path": "/tmp", "limit": 1},
            headers={"X-API-Key": "secret-test-key"},
        )
        assert response.status_code == 200
    finally:
        _clear_auth_env()


def test_get_endpoint_does_not_require_api_key() -> None:
    try:
        _set_auth_env(True, "secret-test-key")
        client = TestClient(_build_app())

        response = client.get("/health")
        assert response.status_code == 200
    finally:
        _clear_auth_env()


def test_production_without_api_key_fails_closed_even_when_disabled() -> None:
    try:
        _set_auth_env(False, "", app_env="production")
        client = TestClient(_build_app())

        response = client.post("/pipeline/run", json={"path": "/tmp", "limit": 1})
        assert response.status_code == 503
        body = response.json()
        assert body["error"]["type"] == "auth_misconfigured"
        assert body["error"]["request_id"] == response.headers["X-Request-ID"]
    finally:
        _clear_auth_env()


def test_production_accepts_valid_key_even_when_flag_is_false() -> None:
    try:
        _set_auth_env(False, "production-secret", app_env="production")
        client = TestClient(_build_app())

        response = client.post(
            "/pipeline/run",
            json={"path": "/tmp", "limit": 1},
            headers={"X-API-Key": "production-secret"},
        )
        assert response.status_code == 200
    finally:
        _clear_auth_env()


def test_production_health_remains_available_without_api_key() -> None:
    try:
        _set_auth_env(False, "", app_env="production")
        client = TestClient(_build_app())

        response = client.get("/health")
        assert response.status_code == 200
    finally:
        _clear_auth_env()


def test_development_can_explicitly_disable_authentication() -> None:
    try:
        _set_auth_env(False, "", app_env="development")
        client = TestClient(_build_app())

        response = client.post("/pipeline/run", json={"path": "/tmp", "limit": 1})
        assert response.status_code == 200
    finally:
        _clear_auth_env()
