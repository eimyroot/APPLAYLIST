from __future__ import annotations

import pytest

from core.analysis.rhythm_contracts import (
    BeatEvent,
    BeatGrid,
    EvidenceProvenance,
    EvidenceStatus,
    RhythmicStructureAnalysis,
)


def provenance() -> EvidenceProvenance:
    return EvidenceProvenance(
        provider="librosa-shadow",
        provider_version="0.10.2",
        algorithm_version="wb006c-librosa-beat-grid-v1",
        method="wb006c-shadow-beat-grid-v1",
        source_analysis_version="0.1.0",
    )


def beat(index: int, time_seconds: float) -> BeatEvent:
    return BeatEvent(
        index=index,
        time_seconds=time_seconds,
        confidence=0.8,
        is_downbeat=None,
    )


def test_unknown_downbeat_is_fail_closed() -> None:
    event = beat(0, 0.5)
    assert event.is_downbeat is None
    assert event.downbeat_confidence is None
    with pytest.raises(ValueError, match="unknown downbeat"):
        BeatEvent(
            index=0,
            time_seconds=0.5,
            confidence=0.8,
            is_downbeat=None,
            downbeat_confidence=0.7,
        )


def test_available_grid_requires_monotonic_beats_and_tempo_confidence() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        BeatGrid(
            status=EvidenceStatus.DERIVED,
            beats=(beat(0, 0.5), beat(1, 0.5)),
            provenance=provenance(),
            tempo_bpm=120.0,
            tempo_confidence=0.8,
        )
    with pytest.raises(ValueError, match="tempo_bpm and tempo_confidence"):
        BeatGrid(
            status=EvidenceStatus.DERIVED,
            beats=(beat(0, 0.5), beat(1, 1.0)),
            provenance=provenance(),
            tempo_bpm=120.0,
        )


def test_unavailable_grid_carries_no_measured_values() -> None:
    unavailable = BeatGrid(
        status=EvidenceStatus.UNAVAILABLE,
        beats=(),
        provenance=provenance(),
        unavailable_reason="NO_BEATS",
    )
    assert unavailable.tempo_bpm is None
    with pytest.raises(ValueError, match="must not carry measured"):
        BeatGrid(
            status=EvidenceStatus.UNAVAILABLE,
            beats=(beat(0, 0.5), beat(1, 1.0)),
            provenance=provenance(),
            unavailable_reason="NO_BEATS",
        )


def test_analysis_rejects_beat_beyond_duration() -> None:
    grid = BeatGrid(
        status=EvidenceStatus.DERIVED,
        beats=(beat(0, 0.5), beat(1, 2.5)),
        provenance=provenance(),
        tempo_bpm=120.0,
        tempo_confidence=0.8,
    )
    with pytest.raises(ValueError, match="exceeds track duration"):
        RhythmicStructureAnalysis(
            track_id="track",
            duration_seconds=2.0,
            beat_grid=grid,
        )
