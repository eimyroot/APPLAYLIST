import os
from importlib import reload

from fastapi.testclient import TestClient

import api.main as main_module
import api.security.auth_gate as auth_gate_module
import api.security.settings as settings_module


def _reload_app():
    reload(settings_module)
    reload(auth_gate_module)
    reload(main_module)
    return main_module.app


def _set_auth_env(enabled: bool, api_key: str) -> None:
    os.environ["AUTH_ENABLED"] = "true" if enabled else "false"
    os.environ["API_KEY"] = api_key


def _clear_auth_env() -> None:
    os.environ.pop("AUTH_ENABLED", None)
    os.environ.pop("API_KEY", None)
    os.environ.pop("API_KEY_HEADER_NAME", None)
    os.environ.pop("APP_ENV", None)


def test_write_endpoint_rejects_missing_api_key_when_auth_enabled() -> None:
    try:
        _set_auth_env(True, "secret-test-key")
        app = _reload_app()
        client = TestClient(app)

        response = client.post("/pipeline/run", json={"path": "/tmp", "limit": 1})
        assert response.status_code == 401
        body = response.json()
        assert body["error"]["type"] == "unauthorized"
    finally:
        _clear_auth_env()
        _reload_app()


def test_write_endpoint_accepts_valid_api_key_when_auth_enabled() -> None:
    try:
        _set_auth_env(True, "secret-test-key")
        app = _reload_app()
        client = TestClient(app)

        response = client.post(
            "/pipeline/run",
            json={"path": "/tmp", "limit": 1},
            headers={"X-API-Key": "secret-test-key"},
        )
        assert response.status_code == 200
    finally:
        _clear_auth_env()
        _reload_app()


def test_get_endpoint_does_not_require_api_key() -> None:
    try:
        _set_auth_env(True, "secret-test-key")
        app = _reload_app()
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
    finally:
        _clear_auth_env()
        _reload_app()
