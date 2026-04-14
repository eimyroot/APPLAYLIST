from pathlib import Path

import numpy as np
import soundfile as sf

from services.structure.structure import StructureAnalyzer


def test_structure_analyzer_returns_shape(tmp_path: Path) -> None:
    sr = 22050
    duration = 4.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    y = 0.05 * np.sin(2 * np.pi * 220.0 * t)
    y[int(sr * 1.0):int(sr * 1.2)] += 0.35 * np.sin(2 * np.pi * 880.0 * t[:int(sr * 0.2)])
    y[int(sr * 2.5):int(sr * 2.7)] += 0.45 * np.sin(2 * np.pi * 660.0 * t[:int(sr * 0.2)])

    audio_path = tmp_path / "structure.wav"
    sf.write(audio_path, y, sr)

    analyzer = StructureAnalyzer()
    result = analyzer.analyze_file(str(audio_path))

    assert result.intro_end >= 0.0
    assert result.outro_start >= result.intro_end
    assert result.peak_time >= 0.0
    assert isinstance(result.drop_candidates, list)
    assert isinstance(result.section_boundaries, list)
