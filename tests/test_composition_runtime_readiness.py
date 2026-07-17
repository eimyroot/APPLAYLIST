from dataclasses import FrozenInstanceError

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from core.config.composition_authority import CompositionAuthorityName
from core.config.composition_runtime import (
    CompositionRuntimeConfigurationError,
    CompositionRuntimeReadiness,
    evaluate_composition_runtime,
)
from core.config.settings import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_runtime_is_ready_with_legacy_authority(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COMPOSITION_AUTHORITY", raising=False)
    monkeypatch.delenv("ENABLE_COMPOSITION_COMPARISON", raising=False)
    monkeypatch.delenv("ENABLE_COMPOSITION_RECEIPTS", raising=False)

    readiness = evaluate_composition_runtime()

    assert readiness == CompositionRuntimeReadiness(
        status="ready",
        authority=CompositionAuthorityName.LEGACY,
        comparison_enabled=False,
        receipts_enabled=False,
    )


def test_invalid_authority_fails_application_construction(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMPOSITION_AUTHORITY", "unsupported")

    with pytest.raises(
        CompositionRuntimeConfigurationError,
        match="invalid composition authority",
    ):
        create_app()


def test_canonical_with_comparison_fails_application_construction(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMPOSITION_AUTHORITY", "canonical")
    monkeypatch.setenv("ENABLE_COMPOSITION_COMPARISON", "true")
    monkeypatch.setenv("ENABLE_COMPOSITION_RECEIPTS", "false")

    with pytest.raises(
        CompositionRuntimeConfigurationError,
        match="cannot be combined",
    ):
        create_app()


def test_receipts_without_comparison_fail_application_construction(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMPOSITION_AUTHORITY", "legacy")
    monkeypatch.setenv("ENABLE_COMPOSITION_COMPARISON", "false")
    monkeypatch.setenv("ENABLE_COMPOSITION_RECEIPTS", "true")

    with pytest.raises(
        CompositionRuntimeConfigurationError,
        match="require composition comparison",
    ):
        create_app()


def test_valid_canonical_configuration_reports_ready(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMPOSITION_AUTHORITY", "canonical")
    monkeypatch.setenv("ENABLE_COMPOSITION_COMPARISON", "false")
    monkeypatch.setenv("ENABLE_COMPOSITION_RECEIPTS", "false")

    application = create_app()
    client = TestClient(application)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "composition_authority": "canonical",
        "composition_comparison_enabled": False,
        "composition_receipts_enabled": False,
    }
    assert application.state.composition_runtime_readiness.authority == (
        CompositionAuthorityName.CANONICAL
    )


def test_health_payload_remains_backward_compatible() -> None:
    readiness = CompositionRuntimeReadiness(
        status="ready",
        authority=CompositionAuthorityName.LEGACY,
        comparison_enabled=False,
        receipts_enabled=False,
    )
    client = TestClient(create_app(composition_readiness=readiness))

    payload = client.get("/health").json()

    assert payload == {
        "status": "ok",
        "app": "APPLAYLIST",
        "env": "development",
        "api_version": "0.1.0",
    }


def test_explicit_readiness_injection_bypasses_environment_resolution(
    monkeypatch,
) -> None:
    monkeypatch.setenv("COMPOSITION_AUTHORITY", "unsupported")
    readiness = CompositionRuntimeReadiness(
        status="ready",
        authority=CompositionAuthorityName.LEGACY,
        comparison_enabled=False,
        receipts_enabled=False,
    )

    application = create_app(composition_readiness=readiness)

    assert application.state.composition_runtime_readiness is readiness


def test_readiness_snapshot_is_immutable() -> None:
    readiness = evaluate_composition_runtime(
        authority="legacy",
        comparison_enabled=False,
        receipts_enabled=False,
    )

    with pytest.raises(FrozenInstanceError):
        readiness.status = "not-ready"
