from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from services.analysis.routed_analysis_service import (
    RoutedAnalysisService,
    create_routed_analysis_service,
)


def _write_test_tone(path: Path) -> None:
    sample_rate = 22050
    duration_seconds = 1.0
    samples = int(sample_rate * duration_seconds)

    timeline = np.linspace(
        0,
        duration_seconds,
        samples,
        endpoint=False,
    )
    audio = 0.2 * np.sin(2 * np.pi * 440 * timeline)

    sf.write(path, audio, sample_rate)


def test_routed_analysis_service_factory() -> None:
    service = create_routed_analysis_service()

    assert isinstance(service, RoutedAnalysisService)


def test_routed_analysis_defaults_to_legacy_mode(
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "legacy-tone.wav"
    _write_test_tone(audio_path)

    result = create_routed_analysis_service().analyze(
        track_id="legacy-track",
        path=audio_path,
        env={},
    )

    assert result.mode == "legacy"
    assert result.provider == "legacy"
    assert result.track_id == "legacy-track"
    assert result.payload["track_id"] == "legacy-track"


def test_routed_analysis_uses_provider_mode_when_enabled(
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "provider-tone.wav"
    _write_test_tone(audio_path)

    result = create_routed_analysis_service().analyze(
        track_id="provider-track",
        path=audio_path,
        env={"APPLAYLIST_PROVIDER_ANALYSIS_ENABLED": "1"},
        provider_names=["baseline"],
    )

    assert result.mode == "provider"
    assert result.provider == "baseline"
    assert result.track_id == "provider-track"
    assert result.payload["track_id"] == "provider-track"


def test_invalid_flag_fails_closed_to_legacy(
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "invalid-flag-tone.wav"
    _write_test_tone(audio_path)

    result = create_routed_analysis_service().analyze(
        track_id="safe-track",
        path=audio_path,
        env={"APPLAYLIST_PROVIDER_ANALYSIS_ENABLED": "maybe"},
    )

    assert result.mode == "legacy"
    assert result.provider == "legacy"
