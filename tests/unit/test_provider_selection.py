from __future__ import annotations

from core.analysis.provider_contracts import available, dependency_missing, unavailable
from core.analysis.provider_selection import select_provider


def test_selects_requested_provider_when_available() -> None:
    result = select_provider(
        requested_provider="essentia",
        configured_default="librosa",
        safe_baseline="baseline",
        availability=[
            available("essentia"),
            available("librosa"),
            available("baseline"),
        ],
    )

    assert result.selected is True
    assert result.provider == "essentia"
    assert result.reason == "requested_provider_available"
    assert result.fallback_used is False


def test_falls_back_to_configured_default_when_requested_missing() -> None:
    result = select_provider(
        requested_provider="essentia",
        configured_default="librosa",
        safe_baseline="baseline",
        availability=[
            dependency_missing("essentia", "essentia"),
            available("librosa"),
            available("baseline"),
        ],
    )

    assert result.provider == "librosa"
    assert result.reason == "configured_default_available"
    assert result.fallback_used is True


def test_falls_back_to_safe_baseline_when_advanced_providers_unavailable() -> None:
    result = select_provider(
        requested_provider="essentia",
        configured_default="librosa",
        safe_baseline="baseline",
        availability=[
            dependency_missing("essentia", "essentia"),
            unavailable("librosa", "disabled"),
            available("baseline"),
        ],
    )

    assert result.provider == "baseline"
    assert result.reason == "safe_baseline_available"
    assert result.fallback_used is True


def test_returns_controlled_no_selection_when_no_provider_available() -> None:
    result = select_provider(
        requested_provider="essentia",
        configured_default="librosa",
        safe_baseline="baseline",
        availability=[
            dependency_missing("essentia", "essentia"),
            unavailable("librosa", "disabled"),
            unavailable("baseline", "disabled"),
        ],
    )

    assert result.selected is False
    assert result.provider is None
    assert result.reason == "no_provider_available"
    assert result.fallback_used is True


def test_selection_uses_metadata_only() -> None:
    result = select_provider(
        requested_provider=None,
        configured_default=None,
        safe_baseline="baseline",
        availability=[available("baseline")],
    )

    assert result.provider == "baseline"
    assert result.reason == "safe_baseline_available"
