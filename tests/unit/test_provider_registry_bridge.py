from __future__ import annotations

import importlib
import sys

from core.analysis.provider_contracts import available, dependency_missing, unavailable
from core.analysis.provider_registry_bridge import (
    ProviderRegistrySelectionConfig,
    select_from_registry_availability,
)


def test_registry_bridge_selects_requested_available_provider() -> None:
    result = select_from_registry_availability(
        config=ProviderRegistrySelectionConfig(
            requested_provider="essentia",
            configured_default="librosa",
            safe_baseline="baseline",
        ),
        availability=[
            available("essentia"),
            available("librosa"),
            available("baseline"),
        ],
    )

    assert result.provider == "essentia"
    assert result.reason == "requested_provider_available"
    assert result.fallback_used is False


def test_registry_bridge_falls_back_to_baseline() -> None:
    result = select_from_registry_availability(
        config=ProviderRegistrySelectionConfig(
            requested_provider="essentia",
            configured_default="librosa",
            safe_baseline="baseline",
        ),
        availability=[
            dependency_missing("essentia", "essentia"),
            unavailable("librosa", "disabled"),
            available("baseline"),
        ],
    )

    assert result.provider == "baseline"
    assert result.reason == "safe_baseline_available"
    assert result.fallback_used is True


def test_registry_bridge_has_controlled_no_selection() -> None:
    result = select_from_registry_availability(
        config=ProviderRegistrySelectionConfig(
            requested_provider="essentia",
            configured_default="librosa",
            safe_baseline="baseline",
        ),
        availability=[
            dependency_missing("essentia", "essentia"),
            unavailable("librosa", "disabled"),
            unavailable("baseline", "disabled"),
        ],
    )

    assert result.selected is False
    assert result.provider is None
    assert result.reason == "no_provider_available"


def test_registry_bridge_import_does_not_force_optional_audio_stack() -> None:
    optional = {"librosa", "numba", "llvmlite", "essentia"}

    before = set(sys.modules)
    importlib.import_module("core.analysis.provider_registry_bridge")
    after = set(sys.modules)

    assert optional.intersection(after - before) == set()
