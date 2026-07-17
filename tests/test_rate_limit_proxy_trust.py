from __future__ import annotations

from ipaddress import ip_network

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.main import create_app
from api.middleware.rate_limit import RateLimitMiddleware, resolve_client_key
from api.security.settings import SecurityConfigurationError, SecuritySettings


def _networks(*values: str):
    return tuple(ip_network(value) for value in values)


def test_default_policy_ignores_forwarded_header() -> None:
    assert resolve_client_key(
        direct_peer="203.0.113.10",
        forwarded_for="198.51.100.1",
        trusted_proxy_depth=0,
        trusted_proxy_networks=(),
    ) == "203.0.113.10"


def test_untrusted_direct_peer_cannot_override_client_identity() -> None:
    assert resolve_client_key(
        direct_peer="203.0.113.10",
        forwarded_for="198.51.100.1",
        trusted_proxy_depth=1,
        trusted_proxy_networks=_networks("10.0.0.0/8"),
    ) == "203.0.113.10"


def test_trusted_one_hop_chain_resolves_original_client() -> None:
    assert resolve_client_key(
        direct_peer="10.0.0.2",
        forwarded_for="198.51.100.7",
        trusted_proxy_depth=1,
        trusted_proxy_networks=_networks("10.0.0.0/8"),
    ) == "198.51.100.7"


def test_trusted_multi_hop_chain_resolves_original_client() -> None:
    assert resolve_client_key(
        direct_peer="10.0.0.3",
        forwarded_for="198.51.100.7, 10.0.0.2",
        trusted_proxy_depth=2,
        trusted_proxy_networks=_networks("10.0.0.0/8"),
    ) == "198.51.100.7"


def test_untrusted_intermediate_proxy_falls_back_to_direct_peer() -> None:
    assert resolve_client_key(
        direct_peer="10.0.0.3",
        forwarded_for="198.51.100.7, 192.0.2.2",
        trusted_proxy_depth=2,
        trusted_proxy_networks=_networks("10.0.0.0/8"),
    ) == "10.0.0.3"


@pytest.mark.parametrize(
    "forwarded_for",
    [None, "", "not-an-ip", "198.51.100.7, not-an-ip"],
)
def test_malformed_forwarded_chain_falls_back_to_direct_peer(
    forwarded_for: str | None,
) -> None:
    assert resolve_client_key(
        direct_peer="10.0.0.3",
        forwarded_for=forwarded_for,
        trusted_proxy_depth=1,
        trusted_proxy_networks=_networks("10.0.0.0/8"),
    ) == "10.0.0.3"


def test_incomplete_forwarded_chain_falls_back_to_direct_peer() -> None:
    assert resolve_client_key(
        direct_peer="10.0.0.3",
        forwarded_for="198.51.100.7",
        trusted_proxy_depth=2,
        trusted_proxy_networks=_networks("10.0.0.0/8"),
    ) == "10.0.0.3"


def test_proxy_depth_without_cidrs_fails_application_startup() -> None:
    config = SecuritySettings(
        app_env="development",
        allowed_origins_raw="*",
        trusted_proxy_depth=1,
        trusted_proxy_cidrs_raw="",
    )

    with pytest.raises(SecurityConfigurationError, match="TRUSTED_PROXY_CIDRS"):
        create_app(config)


def test_invalid_proxy_cidr_fails_application_startup() -> None:
    config = SecuritySettings(
        app_env="development",
        allowed_origins_raw="*",
        trusted_proxy_depth=1,
        trusted_proxy_cidrs_raw="not-a-cidr",
    )

    with pytest.raises(SecurityConfigurationError, match="Invalid TRUSTED_PROXY_CIDRS"):
        create_app(config)


def test_rotating_forwarded_header_does_not_bypass_default_rate_limit() -> None:
    app = FastAPI()

    @app.get("/probe")
    def probe() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(
        RateLimitMiddleware,
        limit_per_minute=1,
        trusted_proxy_depth=0,
        trusted_proxy_networks=(),
    )
    client = TestClient(app)

    first = client.get("/probe", headers={"X-Forwarded-For": "198.51.100.1"})
    second = client.get("/probe", headers={"X-Forwarded-For": "198.51.100.2"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"] == "rate_limit_exceeded"
