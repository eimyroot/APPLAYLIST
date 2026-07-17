from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.security.settings import SecurityConfigurationError, SecuritySettings


def _settings(*, app_env: str, origins: str) -> SecuritySettings:
    return SecuritySettings(
        app_env=app_env,
        allowed_origins_raw=origins,
        enable_rate_limit=False,
    )


@pytest.mark.parametrize("origins", ["*", "", "   "])
def test_production_rejects_wildcard_or_empty_origins(origins: str) -> None:
    with pytest.raises(SecurityConfigurationError, match="explicit non-wildcard"):
        create_app(_settings(app_env="production", origins=origins))


def test_cors_origin_list_is_normalized_and_deduplicated() -> None:
    config = _settings(
        app_env="production",
        origins=" https://app.example.com,https://admin.example.com,https://app.example.com ",
    )

    assert config.allowed_origins == [
        "https://app.example.com",
        "https://admin.example.com",
    ]
    assert config.cors_allow_credentials is True


def test_cors_rejects_wildcard_mixed_with_explicit_origins() -> None:
    config = _settings(
        app_env="development",
        origins="*,https://app.example.com",
    )

    with pytest.raises(SecurityConfigurationError, match="cannot combine"):
        _ = config.allowed_origins


def test_explicit_production_origin_receives_credentialed_preflight_headers() -> None:
    client = TestClient(
        create_app(
            _settings(
                app_env="production",
                origins="https://app.example.com",
            )
        )
    )

    response = client.options(
        "/pipeline/run",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,X-API-Key",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://app.example.com"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_unlisted_production_origin_receives_no_allow_origin_header() -> None:
    client = TestClient(
        create_app(
            _settings(
                app_env="production",
                origins="https://app.example.com",
            )
        )
    )

    response = client.options(
        "/pipeline/run",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_development_wildcard_disables_cors_credentials() -> None:
    client = TestClient(create_app(_settings(app_env="development", origins="*")))

    response = client.get(
        "/health",
        headers={"Origin": "https://local-tool.example.com"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in response.headers
