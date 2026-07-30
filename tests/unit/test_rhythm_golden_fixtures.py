from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path

from tests.fixtures.rhythm.generate_golden_fixtures import generate

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "rhythm"
MANIFEST_PATH = FIXTURE_ROOT / "golden_manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_golden_fixture_bytes_match_manifest(tmp_path: Path) -> None:
    expected = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    actual = generate(tmp_path)
    assert actual == expected
    for fixture in actual["fixtures"]:
        assert sha256(tmp_path / fixture["name"]) == fixture["sha256"]


def test_golden_fixture_wave_geometry_matches_manifest(tmp_path: Path) -> None:
    manifest = generate(tmp_path)
    for fixture in manifest["fixtures"]:
        with wave.open(str(tmp_path / fixture["name"]), "rb") as wav:
            assert wav.getframerate() == fixture["sample_rate"]
            assert wav.getnchannels() == fixture["channels"]
            assert wav.getsampwidth() == fixture["sample_width_bytes"]
            duration = wav.getnframes() / wav.getframerate()
            assert duration == fixture["duration_seconds"]


def test_degraded_fixture_has_lower_peak_than_clean(tmp_path: Path) -> None:
    generate(tmp_path)

    def peak(path: Path) -> int:
        with wave.open(str(path), "rb") as wav:
            frames = wav.readframes(wav.getnframes())
        values = [
            int.from_bytes(frames[index:index + 2], "little", signed=True)
            for index in range(0, len(frames), 2)
        ]
        return max(abs(value) for value in values)

    assert peak(tmp_path / "degraded_phrase_16.wav") < peak(
        tmp_path / "pulse_phrase_16.wav"
    )


def test_silence_fixture_is_exactly_zero(tmp_path: Path) -> None:
    generate(tmp_path)
    with wave.open(str(tmp_path / "silence_4s.wav"), "rb") as wav:
        frames = wav.readframes(wav.getnframes())
    assert set(frames) == {0}
