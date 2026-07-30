from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import wave
from dataclasses import dataclass
from pathlib import Path

SAMPLE_RATE = 8000
BPM = 120.0
BEAT_INTERVAL_SECONDS = 60.0 / BPM
GENERATOR_VERSION = "wb006b-golden-rhythm-v1"


@dataclass(frozen=True)
class FixtureSpec:
    name: str
    kind: str
    total_beats: int
    phrase_length_beats: int | None
    degraded: bool = False
    silence_seconds: float | None = None


SPECS = (
    FixtureSpec("pulse_phrase_8.wav", "pulse", 64, 8),
    FixtureSpec("pulse_phrase_16.wav", "pulse", 64, 16),
    FixtureSpec("pulse_phrase_32.wav", "pulse", 64, 32),
    FixtureSpec("structured_64beats.wav", "structured", 64, 16),
    FixtureSpec("degraded_phrase_16.wav", "pulse", 64, 16, degraded=True),
    FixtureSpec("silence_4s.wav", "silence", 0, None, silence_seconds=4.0),
)


def _clip_int16(value: float) -> int:
    return max(-32768, min(32767, int(round(value * 32767.0))))


def _lcg_noise(length: int, seed: int = 0xC0FFEE) -> list[float]:
    state = seed & 0x7FFFFFFF
    output: list[float] = []
    for _ in range(length):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        output.append(((state / 0x7FFFFFFF) * 2.0) - 1.0)
    return output


def _click(
    samples: list[float],
    start: int,
    amplitude: float,
    frequency: float,
) -> None:
    click_length = int(SAMPLE_RATE * 0.035)
    for offset in range(click_length):
        index = start + offset
        if index >= len(samples):
            break
        envelope = math.exp(-8.0 * offset / max(1, click_length - 1))
        samples[index] += amplitude * envelope * math.sin(
            2.0 * math.pi * frequency * offset / SAMPLE_RATE
        )


def _pulse_fixture(spec: FixtureSpec) -> list[float]:
    assert spec.phrase_length_beats is not None
    duration = spec.total_beats * BEAT_INTERVAL_SECONDS
    samples = [0.0] * int(round(duration * SAMPLE_RATE))
    for beat_index in range(spec.total_beats):
        start = int(round(beat_index * BEAT_INTERVAL_SECONDS * SAMPLE_RATE))
        is_downbeat = beat_index % 4 == 0
        is_phrase = beat_index % spec.phrase_length_beats == 0
        amplitude = 0.34
        frequency = 900.0
        if is_downbeat:
            amplitude = 0.58
            frequency = 700.0
        if is_phrase:
            amplitude = 0.82
            frequency = 520.0
        if spec.degraded:
            amplitude *= 0.24
        _click(samples, start, amplitude, frequency)

    if spec.degraded:
        noise = _lcg_noise(len(samples))
        for index, value in enumerate(noise):
            samples[index] += value * 0.085
    return samples


def _structured_fixture(spec: FixtureSpec) -> list[float]:
    duration = spec.total_beats * BEAT_INTERVAL_SECONDS
    samples = [0.0] * int(round(duration * SAMPLE_RATE))
    section_ranges = (
        (0, 8, 0.26, 180.0),
        (8, 24, 0.46, 220.0),
        (24, 32, 0.18, 150.0),
        (32, 48, 0.72, 260.0),
        (48, 64, 0.30, 190.0),
    )
    for beat_index in range(spec.total_beats):
        start = int(round(beat_index * BEAT_INTERVAL_SECONDS * SAMPLE_RATE))
        section = next(
            item for item in section_ranges if item[0] <= beat_index < item[1]
        )
        _, _, section_amplitude, tone_frequency = section
        is_downbeat = beat_index % 4 == 0
        is_phrase = beat_index in {0, 8, 24, 32, 48}
        click_amplitude = section_amplitude * (1.25 if is_downbeat else 0.8)
        if is_phrase:
            click_amplitude = min(0.9, click_amplitude + 0.22)
        _click(samples, start, click_amplitude, 600.0 if is_phrase else 920.0)

        end = min(len(samples), start + int(BEAT_INTERVAL_SECONDS * SAMPLE_RATE))
        for index in range(start, end):
            local = (index - start) / SAMPLE_RATE
            samples[index] += section_amplitude * 0.09 * math.sin(
                2.0 * math.pi * tone_frequency * local
            )
    return samples


def _write_wave(path: Path, samples: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = b"".join(struct.pack("<h", _clip_int16(sample)) for sample in samples)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(frames)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate(output_dir: Path) -> dict[str, object]:
    fixtures: list[dict[str, object]] = []
    for spec in SPECS:
        if spec.kind == "silence":
            assert spec.silence_seconds is not None
            samples = [0.0] * int(round(spec.silence_seconds * SAMPLE_RATE))
            duration = spec.silence_seconds
        elif spec.kind == "structured":
            samples = _structured_fixture(spec)
            duration = spec.total_beats * BEAT_INTERVAL_SECONDS
        else:
            samples = _pulse_fixture(spec)
            duration = spec.total_beats * BEAT_INTERVAL_SECONDS

        path = output_dir / spec.name
        _write_wave(path, samples)
        beat_times = [
            round(index * BEAT_INTERVAL_SECONDS, 6)
            for index in range(spec.total_beats)
        ]
        downbeat_times = beat_times[::4]
        phrase_boundaries = []
        if spec.kind == "structured":
            phrase_boundaries = [4.0, 12.0, 16.0, 24.0]
        elif spec.phrase_length_beats is not None:
            phrase_boundaries = [
                round(index * BEAT_INTERVAL_SECONDS, 6)
                for index in range(
                    spec.phrase_length_beats,
                    spec.total_beats,
                    spec.phrase_length_beats,
                )
            ]

        fixtures.append(
            {
                "name": spec.name,
                "kind": spec.kind,
                "sample_rate": SAMPLE_RATE,
                "channels": 1,
                "sample_width_bytes": 2,
                "duration_seconds": round(duration, 6),
                "bpm": BPM if spec.total_beats else None,
                "total_beats": spec.total_beats,
                "phrase_length_beats": spec.phrase_length_beats,
                "beat_times_seconds": beat_times,
                "downbeat_times_seconds": downbeat_times,
                "phrase_boundaries_seconds": phrase_boundaries,
                "degraded": spec.degraded,
                "sha256": _sha256(path),
            }
        )

    manifest = {
        "schema_version": "rhythm-golden-manifest-v1",
        "generator_version": GENERATOR_VERSION,
        "fixtures": fixtures,
    }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    manifest = generate(args.output_dir)
    serialized = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
