from pathlib import Path

import numpy as np
import soundfile as sf

from services.analysis.analyzer import AudioAnalyzer


def test_audio_analyzer_persists_analysis(tmp_path: Path) -> None:
    sr = 22050
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    y = 0.2 * np.sin(2 * np.pi * 440.0 * t)

    audio_path = tmp_path / "tone.wav"
    sf.write(audio_path, y, sr)

    analyzer = AudioAnalyzer()
    result = analyzer.analyze_file(track_id="track-analysis-1", path=str(audio_path))

    assert result.track_id == "track-analysis-1"
    assert result.extractor_backend == "librosa"
    assert result.extractor_name == "bundle-4-audio-analyzer"
    assert result.duration_seconds is not None
    assert result.duration_seconds > 1.5
    assert result.energy is not None
    assert 0.0 <= result.energy <= 1.0
