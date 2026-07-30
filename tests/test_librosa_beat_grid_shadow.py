from __future__ import annotations

import hashlib
import struct
import wave
from pathlib import Path

import numpy as np
import pytest

from core.analysis.rhythm_contracts import EvidenceStatus, SourceAudioIdentity
from core.analysis.rhythm_reconciliation import (
    CanonicalTempoEvidence,
    TempoRelationship,
    reconcile_shadow_beat_grid,
)
from services.analysis.librosa_beat_grid_shadow import LibrosaBeatGridShadowAnalyzer

SAMPLE_RATE = 22_050


def _write_click_track(path: Path, *, bpm: float = 120.0, beats: int = 32) -> float:
    interval = 60.0 / bpm
    duration = beats * interval
    sample_count = int(round(duration * SAMPLE_RATE))
    samples = np.zeros(sample_count, dtype=np.float64)
    click_length = int(0.035 * SAMPLE_RATE)
    window = np.hanning(click_length)
    rng = np.random.default_rng(6006)
    pulse = rng.normal(0.0, 1.0, click_length) * window
    pulse /= max(float(np.max(np.abs(pulse))), 1e-12)
    for beat_index in range(beats):
        start = int(round(beat_index * interval * SAMPLE_RATE))
        end = min(sample_count, start + click_length)
        amplitude = 0.85 if beat_index % 4 == 0 else 0.60
        samples[start:end] += pulse[: end - start] * amplitude
    samples = np.clip(samples, -0.98, 0.98)
    frames = b"".join(struct.pack("<h", int(round(value * 32767.0))) for value in samples)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(frames)
    return duration


def _write_silence(path: Path, *, duration: float = 4.0) -> float:
    sample_count = int(round(duration * SAMPLE_RATE))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"\x00\x00" * sample_count)
    return duration


def _source_identity(path: Path) -> SourceAudioIdentity:
    resolved = path.resolve(strict=True)
    return SourceAudioIdentity(
        resolved_path=str(resolved),
        sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        size_bytes=resolved.stat().st_size,
    )


def canonical(
    track_id: str,
    *,
    source: Path,
    duration: float,
    bpm: float | None = 120.0,
) -> CanonicalTempoEvidence:
    return CanonicalTempoEvidence(
        track_id=track_id,
        provider="baseline",
        provider_version="0.1.0",
        algorithm_version="bundle-4-audio-analyzer",
        source_analysis_version="0.1.0",
        source_identity=_source_identity(source),
        duration_seconds=duration,
        bpm=bpm,
        bpm_confidence=None,
    )


def test_shadow_analyzer_emits_read_only_beat_grid(tmp_path: Path) -> None:
    source = tmp_path / "clicks.wav"
    duration = _write_click_track(source)
    evidence = canonical("track", source=source, duration=duration)

    result = LibrosaBeatGridShadowAnalyzer().analyze(
        str(source.resolve()),
        canonical_evidence=evidence,
        track_id="track",
    )

    assert result.beat_grid.status is EvidenceStatus.DERIVED
    assert len(result.beat_grid.beats) >= 2
    assert result.beat_grid.tempo_bpm is not None
    assert result.beat_grid.tempo_confidence is not None
    assert result.beat_grid.provenance.source_identity == evidence.source_identity
    assert all(beat.is_downbeat is None for beat in result.beat_grid.beats)
    assert result.beat_grid.meter_beats_per_bar is None
    reconciliation = reconcile_shadow_beat_grid(evidence, result.beat_grid)
    assert reconciliation.relationship in {
        TempoRelationship.DIRECT,
        TempoRelationship.HALF_TIME,
        TempoRelationship.DOUBLE_TIME,
    }
    assert reconciliation.within_tolerance is True


def test_shadow_analyzer_returns_unavailable_for_silence(tmp_path: Path) -> None:
    source = tmp_path / "silence.wav"
    duration = _write_silence(source)
    result = LibrosaBeatGridShadowAnalyzer().analyze(
        str(source.resolve()),
        canonical_evidence=canonical("silence", source=source, duration=duration),
        track_id="silence",
    )
    assert result.beat_grid.status is EvidenceStatus.UNAVAILABLE
    assert result.beat_grid.beats == ()
    assert result.beat_grid.unavailable_reason == "SILENT_AUDIO"


def test_shadow_analyzer_rejects_track_binding_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "clicks.wav"
    duration = _write_click_track(source)
    evidence = canonical("canonical-track", source=source, duration=duration)
    with pytest.raises(ValueError, match="track_id"):
        LibrosaBeatGridShadowAnalyzer().analyze(
            str(source.resolve()),
            canonical_evidence=evidence,
            track_id="other-track",
        )


def test_shadow_analyzer_rejects_different_source_path_with_same_duration(
    tmp_path: Path,
) -> None:
    canonical_source = tmp_path / "canonical.wav"
    shadow_source = tmp_path / "shadow.wav"
    duration = _write_click_track(canonical_source)
    _write_click_track(shadow_source)
    evidence = canonical("track", source=canonical_source, duration=duration)

    with pytest.raises(ValueError, match="path does not match"):
        LibrosaBeatGridShadowAnalyzer().analyze(
            str(shadow_source.resolve()),
            canonical_evidence=evidence,
            track_id="track",
        )


def test_shadow_analyzer_rejects_content_change_after_source_binding(tmp_path: Path) -> None:
    source = tmp_path / "track.wav"
    duration = _write_click_track(source)
    evidence = canonical("track", source=source, duration=duration)
    _write_silence(source, duration=duration)

    with pytest.raises(ValueError, match="SHA-256"):
        LibrosaBeatGridShadowAnalyzer().analyze(
            str(source.resolve()),
            canonical_evidence=evidence,
            track_id="track",
        )
