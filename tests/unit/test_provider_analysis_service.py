from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from core.analysis.contracts import CanonicalAnalysisResult
from core.analysis.provider_errors import ProviderError
from services.analysis.provider_analysis_service import (
    ProviderAnalysisService,
    create_provider_analysis_service,
)


def _write_test_tone(path: Path) -> None:
    sample_rate = 22050
    duration_seconds = 1.0
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False)
    audio = 0.2 * np.sin(2 * np.pi * 440 * t)
    sf.write(path, audio, sample_rate)


def test_provider_analysis_service_factory() -> None:
    service = create_provider_analysis_service()

    assert isinstance(service, ProviderAnalysisService)


def test_provider_analysis_service_runs_baseline_provider(tmp_path: Path) -> None:
    audio_path = tmp_path / "tone.wav"
    _write_test_tone(audio_path)

    service = create_provider_analysis_service()
    output = service.analyze(
        track_id="track-1",
        path=audio_path,
        provider_names=["baseline"],
    )

    assert output.provider == "baseline"
    assert isinstance(output.normalized, CanonicalAnalysisResult)
    assert output.normalized.track_id == "track-1"
    assert output.normalized.duration_seconds is not None
    assert output.normalized.duration_seconds > 0


def test_provider_analysis_service_returns_controlled_error_when_no_provider_available(
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "tone.wav"
    _write_test_tone(audio_path)

    service = create_provider_analysis_service()

    with pytest.raises(ProviderError) as exc_info:
        service.analyze(
            track_id="track-1",
            path=audio_path,
            requested_provider="missing-provider",
            safe_baseline="missing-baseline",
            provider_names=["missing-provider", "missing-baseline"],
        )

    assert exc_info.value.details.code == "provider_unavailable"
