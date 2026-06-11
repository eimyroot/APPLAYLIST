from __future__ import annotations

from core.analysis.provider_errors import (
    ProviderError,
    provider_dependency_missing,
    provider_output_invalid,
    provider_runtime_error,
    provider_unavailable,
)


def test_provider_unavailable_error_has_controlled_details() -> None:
    error = provider_unavailable("essentia", "Provider disabled")

    assert isinstance(error, ProviderError)
    assert error.details.code == "provider_unavailable"
    assert error.details.provider == "essentia"
    assert error.details.recoverable is True


def test_provider_dependency_missing_is_recoverable() -> None:
    error = provider_dependency_missing("essentia", "essentia")

    assert error.details.code == "provider_dependency_missing"
    assert "essentia" in error.details.message
    assert error.details.recoverable is True


def test_provider_runtime_error_is_not_recoverable() -> None:
    error = provider_runtime_error("librosa", "analysis failed")

    assert error.details.code == "provider_runtime_error"
    assert error.details.recoverable is False


def test_provider_output_invalid_is_not_recoverable() -> None:
    error = provider_output_invalid("baseline", "missing bpm")

    assert error.details.code == "provider_output_invalid"
    assert error.details.recoverable is False
