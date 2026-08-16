from __future__ import annotations

from dataclasses import asdict

import pytest

from core.analysis.provider_contract import CanonicalAnalysisResult
from core.intelligence.music_dna import FactStatus, build_music_dna
from core.intelligence.transition_contract import (
    TransitionContext,
    TransitionStrategy,
    TransitionWeights,
)
from services.intelligence.transition_engine import (
    assess_transition,
    preserve_groove_context_v1,
)


def canonical(**overrides: object) -> CanonicalAnalysisResult:
    values: dict[str, object] = {
        "path": "/Users/private/Music/secret-track.wav",
        "provider": "librosa",
        "bpm": 128.0,
        "bpm_confidence": 0.91,
        "key": "8A",
        "key_confidence": 0.84,
        "energy": 0.62,
        "loudness_db": -10.0,
        "duration_seconds": 300.0,
        "genre_hint": "techno",
        "key_tonic": "A",
        "key_scale": "minor",
        "camelot": "8A",
        "beat_stability": 0.94,
        "harmonic_ratio": 0.55,
        "percussive_ratio": 0.72,
        "provider_version": "0.10.2",
        "algorithm_version": "baseline-librosa-mir-v1",
    }
    values.update(overrides)
    return CanonicalAnalysisResult(**values)  # type: ignore[arg-type]


def dna(track_id: str, **overrides: object):
    return build_music_dna(
        track_id=track_id,
        content_identity=f"sha256:{track_id}",
        analysis_revision=f"analysis:{track_id}:1",
        evidence_id=f"evidence:{track_id}:1",
        input_identity=f"input:{track_id}",
        canonical=canonical(**overrides),
        benchmark_status="benchmark-candidate",
    )


def test_music_dna_is_path_free_and_marks_missing_timing_evidence() -> None:
    result = dna("track-a")
    serialized = repr(asdict(result))

    assert "/Users/private" not in serialized
    assert "secret-track.wav" not in serialized
    assert result.rhythm.timing_status is FactStatus.UNAVAILABLE
    assert result.segments[0].segment_id == "track-a:whole"
    assert result.segments[0].structural_label == "unknown"
    assert result.segments[0].evidence_codes == ("whole_track_fallback",)


def test_music_dna_preserves_explicit_tempo_family_hypotheses() -> None:
    result = dna("track-a", bpm=128.0)
    hypotheses = {
        (item.bpm, item.relation_to_primary, item.status) for item in result.rhythm.bpm_hypotheses
    }

    assert (128.0, "primary", FactStatus.MEASURED) in hypotheses
    assert (64.0, "half_time", FactStatus.DERIVED) in hypotheses
    assert (256.0, "double_time", FactStatus.DERIVED) in hypotheses


def test_music_dna_fails_closed_without_provenance_versions() -> None:
    with pytest.raises(ValueError, match="explicit provider and algorithm versions"):
        dna("track-a", provider_version=None)


def test_half_double_time_family_can_match_without_faking_primary_bpm() -> None:
    source = dna("track-a", bpm=128.0)
    target = dna("track-b", bpm=64.0, camelot="8A", key="8A")

    assessment = assess_transition(
        source=source,
        source_segment_id="track-a:whole",
        target=target,
        target_segment_id="track-b:whole",
        context=preserve_groove_context_v1(),
        created_at="2026-08-17T00:00:00Z",
    )

    assert assessment.compatibility_vector.tempo_fit == pytest.approx(1.0)
    assert assessment.cost_vector.tempo_change_percent == pytest.approx(0.0)
    assert TransitionStrategy.HALF_DOUBLE_TIME_SWITCH in {
        item.strategy for item in assessment.candidate_strategies
    }
    assert any(item.code == "tempo_family_match" for item in assessment.explanations)


def test_contextual_projection_is_scored_only_inside_named_context() -> None:
    source = dna("track-a", bpm=128.0, camelot="8A", key="8A")
    target = dna("track-b", bpm=130.0, camelot="9A", key="9A")

    assessment = assess_transition(
        source=source,
        source_segment_id="track-a:whole",
        target=target,
        target_segment_id="track-b:whole",
        context=preserve_groove_context_v1(),
        created_at="2026-08-17T00:00:00Z",
    )

    assert assessment.compatibility_vector.harmonic_fit == pytest.approx(0.9)
    assert assessment.contextual_projection.context_id == "preserve-groove"
    assert assessment.contextual_projection.context_version == "1"
    assert assessment.contextual_projection.score is not None
    assert 0.0 <= assessment.contextual_projection.score <= 1.0


def test_hard_tempo_constraint_blocks_instead_of_being_outweighed() -> None:
    source = dna("track-a", bpm=128.0)
    target = dna("track-b", bpm=130.0)
    strict = TransitionContext(
        context_id="strict-tempo",
        context_version="1",
        goal="hold_tempo",
        desired_energy_direction=None,
        max_tempo_change_percent=0.1,
        minimum_harmonic_fit=None,
        require_phrase_evidence=False,
        allowed_strategies=(TransitionStrategy.CUT,),
        weights=TransitionWeights(),
    )

    assessment = assess_transition(
        source=source,
        source_segment_id="track-a:whole",
        target=target,
        target_segment_id="track-b:whole",
        context=strict,
        created_at="2026-08-17T00:00:00Z",
    )

    assert assessment.contextual_projection.score is None
    assert "tempo_change_exceeds_context" in assessment.contextual_projection.blocked_reasons


def test_missing_tempo_evidence_blocks_context_and_remains_explicit() -> None:
    source = dna("track-a", bpm=None, bpm_confidence=None)
    target = dna("track-b", bpm=130.0)

    assessment = assess_transition(
        source=source,
        source_segment_id="track-a:whole",
        target=target,
        target_segment_id="track-b:whole",
        context=preserve_groove_context_v1(),
        created_at="2026-08-17T00:00:00Z",
    )

    assert assessment.compatibility_vector.tempo_fit is None
    assert assessment.cost_vector.tempo_change_percent is None
    assert "tempo_evidence_missing" in assessment.contextual_projection.blocked_reasons


def test_unbenchmarked_future_risks_are_not_invented() -> None:
    source = dna("track-a")
    target = dna("track-b", loudness_db=-18.0)

    assessment = assess_transition(
        source=source,
        source_segment_id="track-a:whole",
        target=target,
        target_segment_id="track-b:whole",
        context=preserve_groove_context_v1(),
        created_at="2026-08-17T00:00:00Z",
    )

    assert assessment.risk_vector.bass_collision is None
    assert assessment.risk_vector.vocal_collision is None
    assert assessment.risk_vector.spectral_masking is None
    assert "bass_collision_unavailable" in assessment.warnings
    assert "vocal_collision_unavailable" in assessment.warnings
    assert "spectral_masking_unavailable" in assessment.warnings
    assert assessment.risk_vector.loudness_discontinuity == pytest.approx(8.0 / 12.0)


def test_transition_identity_and_projection_are_deterministic_for_same_inputs() -> None:
    source = dna("track-a")
    target = dna("track-b", bpm=129.0, camelot="9A", key="9A")
    kwargs = {
        "source": source,
        "source_segment_id": "track-a:whole",
        "target": target,
        "target_segment_id": "track-b:whole",
        "context": preserve_groove_context_v1(),
        "created_at": "2026-08-17T00:00:00Z",
    }

    first = assess_transition(**kwargs)
    second = assess_transition(**kwargs)

    assert first == second
    assert first.identity.transition_id == second.identity.transition_id


def test_transition_rejects_self_edges() -> None:
    source = dna("track-a")
    with pytest.raises(ValueError, match="must be different"):
        assess_transition(
            source=source,
            source_segment_id="track-a:whole",
            target=source,
            target_segment_id="track-a:whole",
            context=preserve_groove_context_v1(),
            created_at="2026-08-17T00:00:00Z",
        )
