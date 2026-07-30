from __future__ import annotations

import pytest

from core.analysis.provider_contract import CanonicalAnalysisResult
from core.analysis.rhythm_contracts import (
    BeatEvent,
    BeatGrid,
    DirectionalOverlapWindow,
    EvidenceProvenance,
    EvidenceStatus,
    PhraseBoundary,
    RhythmicStructureAnalysis,
    StructuralLabel,
    StructuralSegment,
)


def provenance() -> EvidenceProvenance:
    return EvidenceProvenance(
        provider="golden",
        provider_version="1.0.0",
        algorithm_version="wb006b-golden-rhythm-v1",
        method="deterministic_fixture",
        source_analysis_version="golden-rhythm-fixture-v1",
    )


def beat(index: int, time_seconds: float) -> BeatEvent:
    return BeatEvent(
        index=index,
        time_seconds=time_seconds,
        confidence=0.9,
        is_downbeat=index % 4 == 0,
        downbeat_confidence=0.8,
        bar_index=index // 4,
        beat_in_bar=(index % 4) + 1,
    )


def canonical_result(**overrides: object) -> CanonicalAnalysisResult:
    values: dict[str, object] = {
        "path": "/tmp/example.wav",
        "provider": "librosa",
        "bpm": 120.0,
        "bpm_confidence": 0.8,
        "key": "8B",
        "key_confidence": 0.7,
        "energy": 0.5,
        "loudness_db": -12.0,
        "duration_seconds": 60.0,
        "genre_hint": None,
        "provider_version": "0.10.2",
        "algorithm_version": "baseline-librosa-mir-v1",
    }
    values.update(overrides)
    return CanonicalAnalysisResult(**values)  # type: ignore[arg-type]


def test_provenance_rejects_empty_fields() -> None:
    with pytest.raises(ValueError, match="provider must not be empty"):
        EvidenceProvenance(
            provider="",
            provider_version="1",
            algorithm_version="algo",
            method="x",
            source_analysis_version="canonical-mir-v1",
        )


def test_provenance_maps_exact_canonical_provider_evidence() -> None:
    result = canonical_result()
    mapped = EvidenceProvenance.from_canonical_analysis(
        result,
        method="beat_grid_extraction",
    )
    assert mapped.provider == result.provider
    assert mapped.provider_version == result.provider_version
    assert mapped.algorithm_version == result.algorithm_version
    assert mapped.source_analysis_version == result.analysis_version


def test_provenance_rejects_missing_canonical_version_evidence() -> None:
    with pytest.raises(ValueError, match="provider_version must be explicit"):
        EvidenceProvenance.from_canonical_analysis(
            canonical_result(provider_version=None),
            method="beat_grid_extraction",
        )
    with pytest.raises(ValueError, match="algorithm_version must be explicit"):
        EvidenceProvenance.from_canonical_analysis(
            canonical_result(algorithm_version=None),
            method="beat_grid_extraction",
        )


def test_unknown_downbeat_is_fail_closed() -> None:
    event = BeatEvent(
        index=0,
        time_seconds=0.0,
        confidence=0.9,
        is_downbeat=None,
    )
    assert event.downbeat_confidence is None
    with pytest.raises(ValueError, match="bar-position evidence"):
        BeatEvent(
            index=0,
            time_seconds=0.0,
            confidence=0.9,
            is_downbeat=None,
            bar_index=0,
            beat_in_bar=1,
        )


def test_known_downbeat_requires_independent_confidence() -> None:
    with pytest.raises(ValueError, match="requires downbeat_confidence"):
        BeatEvent(
            index=0,
            time_seconds=0.0,
            confidence=0.9,
            is_downbeat=True,
        )


def test_beat_grid_requires_strictly_increasing_times() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        BeatGrid(
            status=EvidenceStatus.MEASURED,
            beats=(beat(0, 0.5), beat(1, 0.5)),
            provenance=provenance(),
            tempo_bpm=120.0,
            tempo_confidence=0.8,
            meter_beats_per_bar=4,
            meter_confidence=0.8,
        )


def test_beat_grid_unavailable_is_fail_closed() -> None:
    unavailable = BeatGrid(
        status=EvidenceStatus.UNAVAILABLE,
        beats=(),
        provenance=provenance(),
        unavailable_reason="NO_RHYTHMIC_EVIDENCE",
    )
    assert unavailable.beats == ()
    assert unavailable.tempo_bpm is None
    with pytest.raises(ValueError, match="must not carry measured"):
        BeatGrid(
            status=EvidenceStatus.UNAVAILABLE,
            beats=(beat(0, 0.0),),
            provenance=provenance(),
            unavailable_reason="NO_RHYTHMIC_EVIDENCE",
        )


def test_meter_value_and_confidence_are_atomic() -> None:
    with pytest.raises(ValueError, match="present together"):
        BeatGrid(
            status=EvidenceStatus.MEASURED,
            beats=(beat(0, 0.0), beat(1, 0.5)),
            provenance=provenance(),
            tempo_bpm=120.0,
            tempo_confidence=0.9,
            meter_beats_per_bar=4,
        )


def test_phrase_boundary_requires_supported_length() -> None:
    with pytest.raises(ValueError, match="one of 8, 16, or 32"):
        PhraseBoundary(
            beat_index=12,
            time_seconds=6.0,
            phrase_length_beats=12,
            confidence=0.8,
            provenance=provenance(),
            evidence_codes=("BOUNDARY",),
        )


def test_structural_segment_requires_positive_duration() -> None:
    with pytest.raises(ValueError, match="greater than"):
        StructuralSegment(
            start_seconds=4.0,
            end_seconds=4.0,
            label=StructuralLabel.GROOVE,
            confidence=0.8,
            provenance=provenance(),
            evidence_codes=("ENERGY_STABLE",),
        )


def test_analysis_rejects_out_of_duration_evidence() -> None:
    grid = BeatGrid(
        status=EvidenceStatus.MEASURED,
        beats=(beat(0, 0.0), beat(1, 0.5)),
        provenance=provenance(),
        tempo_bpm=120.0,
        tempo_confidence=0.9,
        meter_beats_per_bar=4,
        meter_confidence=0.8,
    )
    boundary = PhraseBoundary(
        beat_index=16,
        time_seconds=8.0,
        phrase_length_beats=16,
        confidence=0.8,
        provenance=provenance(),
        evidence_codes=("NOVELTY_PEAK",),
    )
    with pytest.raises(ValueError, match="exceeds track duration"):
        RhythmicStructureAnalysis(
            track_id="track",
            duration_seconds=4.0,
            beat_grid=grid,
            phrase_boundaries=(boundary,),
        )


def test_overlap_window_requires_consistent_beat_count() -> None:
    with pytest.raises(ValueError, match="equal both directional"):
        DirectionalOverlapWindow(
            source_start_beat=48,
            source_end_beat=64,
            target_start_beat=0,
            target_end_beat=8,
            overlap_beats=16,
            confidence=0.8,
            provenance=provenance(),
            evidence_codes=("PHRASE_ALIGNED",),
        )
