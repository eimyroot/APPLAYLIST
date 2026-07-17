from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
import soundfile as sf

from core.analysis.provider_contract import ProviderOutputInvalid, ProviderRuntimeFailure
from core.analysis.provider_service import RoutedAnalysisService
from core.analysis.providers import LibrosaAnalyzerProvider
from services.analysis.librosa_baseline import BaselineLibrosaMIR, MAJOR_PROFILE


SAMPLE_RATE = 22_050


def _write_synthetic_track(
    path: Path,
    *,
    duration: float = 12.0,
    bpm: float = 120.0,
    amplitude: float = 0.45,
) -> None:
    sample_count = int(SAMPLE_RATE * duration)
    times = np.arange(sample_count, dtype=np.float64) / SAMPLE_RATE

    chord = (
        np.sin(2.0 * np.pi * 261.6256 * times)
        + np.sin(2.0 * np.pi * 329.6276 * times)
        + np.sin(2.0 * np.pi * 391.9954 * times)
    ) / 3.0
    chord *= amplitude * 0.55

    clicks = np.zeros(sample_count, dtype=np.float64)
    pulse_length = max(32, int(SAMPLE_RATE * 0.035))
    rng = np.random.default_rng(45)
    pulse = rng.normal(0.0, 1.0, pulse_length) * np.hanning(pulse_length)
    pulse /= max(float(np.max(np.abs(pulse))), 1e-12)
    pulse *= amplitude * 0.75
    period = int(round(SAMPLE_RATE * 60.0 / bpm))
    for start in range(0, sample_count, period):
        end = min(sample_count, start + pulse_length)
        clicks[start:end] += pulse[: end - start]

    signal = np.clip(chord + clicks, -0.98, 0.98).astype(np.float32)
    sf.write(path, signal, SAMPLE_RATE, subtype="FLOAT")


def test_provider_modules_remain_lazy_on_import() -> None:
    code = """
import sys
import core.analysis.providers
import core.analysis.provider_service
assert 'librosa' not in sys.modules
assert 'soundfile' not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr


def test_real_synthetic_audio_returns_canonical_mir_evidence(tmp_path: Path) -> None:
    source = tmp_path / "c-major-120.wav"
    _write_synthetic_track(source)

    result = RoutedAnalysisService().analyze_path(
        str(source.resolve()),
        preferred_provider="librosa",
    )

    assert result.provider == "librosa"
    assert result.provider_version
    assert result.algorithm_version == "baseline-librosa-mir-v1"
    assert result.duration_seconds == pytest.approx(12.0, abs=0.05)
    assert result.bpm is not None
    assert min(abs(result.bpm - candidate) for candidate in (60.0, 120.0, 240.0)) < 5.0
    assert result.bpm_confidence is not None
    assert 0.0 <= result.bpm_confidence <= 1.0
    assert result.beat_stability is not None
    assert 0.0 <= result.beat_stability <= 1.0
    assert result.key_tonic is not None
    assert result.key_scale in {"major", "minor"}
    assert result.camelot is not None
    assert result.key == result.camelot
    assert result.key_confidence is not None
    assert 0.0 <= result.key_confidence <= 1.0
    assert result.energy is not None
    assert 0.0 <= result.energy <= 1.0
    assert result.loudness_db is not None
    assert result.harmonic_ratio is not None
    assert result.percussive_ratio is not None
    assert result.harmonic_ratio + result.percussive_ratio == pytest.approx(1.0, abs=1e-6)
    assert "baseline provider output is not benchmark-approved" in result.warnings


def test_ideal_c_major_profile_maps_to_camelot_8b() -> None:
    chroma = np.repeat(np.asarray(MAJOR_PROFILE, dtype=float)[:, None], 8, axis=1)

    tonic, scale, camelot, confidence = BaselineLibrosaMIR()._key_evidence(
        chroma,
        np=np,
    )

    assert tonic == "C"
    assert scale == "major"
    assert camelot == "8B"
    assert 0.0 < confidence <= 1.0


def test_fixed_audio_produces_deterministic_raw_result(tmp_path: Path) -> None:
    source = tmp_path / "deterministic.wav"
    _write_synthetic_track(source, duration=6.0)
    provider = LibrosaAnalyzerProvider()

    first = provider.analyze(str(source.resolve()))
    second = provider.analyze(str(source.resolve()))

    assert first == second


def test_silent_audio_is_a_controlled_provider_failure(tmp_path: Path) -> None:
    source = tmp_path / "silence.wav"
    sf.write(source, np.zeros(SAMPLE_RATE * 2, dtype=np.float32), SAMPLE_RATE)

    with pytest.raises(ProviderRuntimeFailure) as exc_info:
        RoutedAnalysisService().analyze_path(
            str(source.resolve()),
            preferred_provider="librosa",
        )

    assert exc_info.value.provider == "librosa"
    assert exc_info.value.code == "provider_runtime_error"


def test_contract_rejects_invalid_camelot_and_warning_shape() -> None:
    service = RoutedAnalysisService(
        selector=lambda _preferred: type(
            "InvalidProvider",
            (),
            {
                "name": "invalid",
                "analyze": lambda self, _path: {
                    "provider": "invalid",
                    "status": "ok",
                    "key": {"camelot": "13A"},
                    "warnings": "not-an-array",
                },
            },
        )()
    )

    with pytest.raises(ProviderOutputInvalid):
        service.analyze_path(str(Path("/tmp/demo.wav")))
