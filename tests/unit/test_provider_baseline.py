from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from core.analysis.provider_baseline import BaselineAnalysisProvider, create_baseline_provider
from core.analysis.provider_contracts import ProviderInput
from core.analysis.provider_errors import ProviderError


def test_baseline_provider_metadata_and_availability() -> None:
    provider = create_baseline_provider()

    assert isinstance(provider, BaselineAnalysisProvider)
    assert provider.metadata.name == "baseline"
    assert provider.metadata.optional_dependencies == ()

    availability = provider.availability()

    assert availability.provider == "baseline"
    assert availability.is_available is True


def test_baseline_provider_analyzes_audio_file(tmp_path: Path) -> None:
    sample_rate = 22050
    duration_seconds = 1.0
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False)
    audio = 0.2 * np.sin(2 * np.pi * 440 * t)

    path = tmp_path / "tone.wav"
    sf.write(path, audio, sample_rate)

    provider = create_baseline_provider()
    output = provider.analyze(
        ProviderInput(
            track_id="track-1",
            path=path,
        )
    )

    assert output.provider == "baseline"
    assert output.backend == "audio-analyzer"
    assert output.normalized["track_id"] == "track-1"
    assert output.normalized["duration_seconds"] > 0


def test_baseline_provider_converts_runtime_failure_to_provider_error() -> None:
    provider = create_baseline_provider()

    with pytest.raises(ProviderError) as exc_info:
        provider.analyze(
            ProviderInput(
                track_id="missing",
                path=Path("/tmp/definitely-missing-applaylist-file.wav"),
            )
        )

    assert exc_info.value.details.code == "provider_runtime_error"
    assert exc_info.value.details.provider == "baseline"
