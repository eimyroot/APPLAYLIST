from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Any

import pytest

import core.analysis.providers as providers_module
from core.analysis.provider_contract import (
    ProviderDependencyMissingError,
    ProviderOutputInvalid,
    ProviderRuntimeFailure,
    ProviderUnavailableError,
    UnknownProviderError,
    normalize_provider_result,
)
from core.analysis.provider_service import RoutedAnalysisService


def test_normalizes_nested_provider_payload() -> None:
    result = normalize_provider_result(
        {
            "provider": "librosa",
            "status": "ok",
            "beat": {"bpm": 128.4, "confidence": 0.91},
            "key": {"camelot": "10A", "confidence": 0.88},
            "metrics": {
                "energy_score": 0.67,
                "loudness_db": -8.4,
                "duration_seconds": 367.2,
            },
            "tags": {"primary_genre_hint": "tech house"},
        },
        path="/tmp/demo.mp3",
        expected_provider="librosa",
    )

    assert result.provider == "librosa"
    assert result.bpm == 128.4
    assert result.bpm_confidence == 0.91
    assert result.key == "10A"
    assert result.key_confidence == 0.88
    assert result.energy == 0.67
    assert result.loudness_db == -8.4
    assert result.duration_seconds == 367.2
    assert result.genre_hint == "tech house"
    assert result.analysis_status == "ok"


def test_nested_values_replace_explicit_top_level_nulls() -> None:
    result = normalize_provider_result(
        {
            "provider": "librosa",
            "status": "ok",
            "bpm": None,
            "energy": None,
            "genre_hint": None,
            "beat": {"bpm": 124.0},
            "metrics": {"energy_score": 0.45},
            "tags": {"primary_genre_hint": "hypnotic techno"},
        },
        path="/tmp/demo.mp3",
    )

    assert result.bpm == 124.0
    assert result.energy == 0.45
    assert result.genre_hint == "hypnotic techno"


def test_flat_key_without_confidence_is_valid() -> None:
    result = normalize_provider_result(
        {
            "provider": "essentia",
            "status": "success",
            "bpm": "130.0",
            "key": "11A",
            "energy": "0.52",
        },
        path="/tmp/demo.wav",
    )

    assert result.key == "11A"
    assert result.key_confidence is None
    assert result.bpm == 130.0
    assert result.energy == 0.52


def test_rejects_malformed_nested_block() -> None:
    with pytest.raises(ProviderOutputInvalid) as exc_info:
        normalize_provider_result(
            {
                "provider": "librosa",
                "status": "ok",
                "metrics": ["not", "an", "object"],
            },
            path="/tmp/demo.wav",
        )

    assert exc_info.value.code == "provider_output_invalid"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("bpm", float("nan")),
        ("energy", float("inf")),
        ("duration_seconds", float("-inf")),
    ],
)
def test_rejects_non_finite_numbers(field: str, value: float) -> None:
    with pytest.raises(ProviderOutputInvalid):
        normalize_provider_result(
            {
                "provider": "librosa",
                "status": "ok",
                field: value,
            },
            path="/tmp/demo.wav",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("bpm", 500),
        ("bpm_confidence", 1.1),
        ("key_confidence", -0.1),
        ("energy", 1.5),
        ("duration_seconds", -1),
    ],
)
def test_rejects_values_outside_contract(field: str, value: float) -> None:
    with pytest.raises(ProviderOutputInvalid):
        normalize_provider_result(
            {
                "provider": "librosa",
                "status": "ok",
                field: value,
            },
            path="/tmp/demo.wav",
        )


def test_rejects_stub_as_success() -> None:
    with pytest.raises(ProviderOutputInvalid) as exc_info:
        normalize_provider_result(
            {
                "provider": "librosa",
                "status": "stub",
            },
            path="/tmp/demo.wav",
        )

    assert "non-success status" in str(exc_info.value)


def test_rejects_provider_identity_mismatch() -> None:
    with pytest.raises(ProviderOutputInvalid):
        normalize_provider_result(
            {
                "provider": "essentia",
                "status": "ok",
            },
            path="/tmp/demo.wav",
            expected_provider="librosa",
        )


def test_preferred_missing_dependency_has_distinct_error(monkeypatch) -> None:
    monkeypatch.setenv("APPLAYLIST_ENABLE_ESSENTIA", "1")
    monkeypatch.setattr(
        providers_module.importlib.util,
        "find_spec",
        lambda _name: None,
    )

    with pytest.raises(ProviderDependencyMissingError) as exc_info:
        providers_module.select_best_provider("essentia")

    assert exc_info.value.code == "provider_dependency_missing"
    assert exc_info.value.provider == "essentia"


@dataclass
class FakeProvider:
    payload: dict[str, Any]
    name: str = "fake"

    def analyze(self, path: str) -> dict[str, Any]:
        return dict(self.payload)


def test_routed_service_returns_only_validated_result() -> None:
    provider = FakeProvider(
        {
            "provider": "fake",
            "status": "completed",
            "bpm": 126,
            "energy": 0.4,
        }
    )
    service = RoutedAnalysisService(selector=lambda _preferred: provider)

    result = service.analyze_path("/tmp/demo.wav")

    assert result.provider == "fake"
    assert result.bpm == 126.0
    assert result.energy == 0.4


def test_routed_service_rejects_current_stub_provider() -> None:
    provider = FakeProvider({"provider": "fake", "status": "stub"})
    service = RoutedAnalysisService(selector=lambda _preferred: provider)

    with pytest.raises(ProviderOutputInvalid):
        service.analyze_path("/tmp/demo.wav")


def test_routed_service_wraps_provider_crash() -> None:
    class CrashingProvider:
        name = "crashing"

        def analyze(self, path: str) -> dict[str, Any]:
            raise OSError("backend crashed")

    service = RoutedAnalysisService(selector=lambda _preferred: CrashingProvider())

    with pytest.raises(ProviderRuntimeFailure) as exc_info:
        service.analyze_path("/tmp/demo.wav")

    assert exc_info.value.code == "provider_runtime_error"
    assert exc_info.value.provider == "crashing"


def test_routed_service_preserves_selection_errors() -> None:
    def unknown_selector(_preferred: str | None):
        raise UnknownProviderError("unknown", provider="missing")

    service = RoutedAnalysisService(selector=unknown_selector)
    with pytest.raises(UnknownProviderError):
        service.analyze_path("/tmp/demo.wav", preferred_provider="missing")

    def unavailable_selector(_preferred: str | None):
        raise ProviderUnavailableError("unavailable", provider="essentia")

    service = RoutedAnalysisService(selector=unavailable_selector)
    with pytest.raises(ProviderUnavailableError):
        service.analyze_path("/tmp/demo.wav", preferred_provider="essentia")


def test_contract_import_does_not_load_optional_audio_backends() -> None:
    code = """
import sys
import core.analysis.provider_contract
import core.analysis.provider_service
assert 'librosa' not in sys.modules
assert 'essentia' not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
