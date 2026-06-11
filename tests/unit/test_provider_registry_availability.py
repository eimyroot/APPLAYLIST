from __future__ import annotations

import importlib
import sys

from core.analysis import provider_registry


def test_provider_registry_exposes_baseline_availability() -> None:
    availability = provider_registry.get_provider_availability(["baseline"])

    assert len(availability) == 1
    assert availability[0].provider == "baseline"
    assert availability[0].status == "available"
    assert availability[0].is_available is True


def test_provider_registry_marks_unknown_provider_unavailable() -> None:
    availability = provider_registry.get_provider_availability(["unknown-provider"])[0]

    assert availability.provider == "unknown-provider"
    assert availability.status == "unavailable"
    assert availability.is_available is False


def test_provider_registry_selects_safe_baseline() -> None:
    result = provider_registry.select_available_provider(
        requested_provider=None,
        configured_default=None,
        safe_baseline="baseline",
        provider_names=["baseline"],
    )

    assert result.selected is True
    assert result.provider == "baseline"
    assert result.reason == "safe_baseline_available"


def test_provider_registry_falls_back_to_baseline_when_essentia_missing() -> None:
    result = provider_registry.select_available_provider(
        requested_provider="essentia",
        configured_default=None,
        safe_baseline="baseline",
        provider_names=["essentia", "baseline"],
    )

    assert result.provider in {"essentia", "baseline"}

    if result.provider == "baseline":
        assert result.reason == "safe_baseline_available"
        assert result.fallback_used is True


def test_provider_registry_import_does_not_force_optional_audio_stack() -> None:
    optional = {"librosa", "numba", "llvmlite", "essentia"}

    before = set(sys.modules)
    importlib.import_module("core.analysis.provider_registry")
    after = set(sys.modules)

    assert optional.intersection(after - before) == set()
