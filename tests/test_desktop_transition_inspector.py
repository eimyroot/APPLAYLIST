from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.intelligence.music_dna import CalibrationState, Confidence
from core.intelligence.transition_contract import (
    ContextualTransitionProjection,
    EnergyDirection,
    TransitionAssessment,
    TransitionCompatibility,
    TransitionCost,
    TransitionEnergyEffect,
    TransitionExplanation,
    TransitionIdentity,
    TransitionRisk,
    TransitionStrategy,
    TransitionStrategyCandidate,
    TransitionWindow,
)
from data.connection import get_sqlite_connection
from data.repositories.music_intelligence_repository import MusicIntelligenceRepository
from data.repositories.playlist_revision_repository import PlaylistRevisionRepository
from services.desktop.transition_inspector_transport import (
    DesktopTransitionInspectorError,
    DesktopTransitionInspectorTransport,
)
from tests.test_desktop_readiness_sidecar import _finish, _request
from tests.test_desktop_set_proposal_transport import _configure_database, _start_extended_sidecar


def _revision() -> dict[str, object]:
    return PlaylistRevisionRepository().append_root(
        source_proposal_id="spr_transition_inspector",
        source_path_id="spp_transition_inspector",
        items=[("trk_a", "A"), ("trk_b", "B"), ("trk_c", "C")],
        operation_metadata={"fixture": "bundle61"},
    )


def _confidence(score: float = 0.8) -> Confidence:
    return Confidence(
        score=score,
        calibration_state=CalibrationState.UNCALIBRATED,
        evidence_count=2,
        disagreement=0.1,
    )


def _assessment(*, context_id: str = "ctx_fixture", context_version: str = "1") -> TransitionAssessment:
    confidence = _confidence()
    return TransitionAssessment(
        identity=TransitionIdentity(
            transition_id="trn_a_b",
            source_track_id="trk_a",
            source_segment_id="seg_a_out",
            target_track_id="trk_b",
            target_segment_id="seg_b_in",
            assessment_version="transition-assessment-v1",
            policy_version="transition-policy-v1",
            music_dna_revision_refs=("mdr_a", "mdr_b"),
            created_at="2026-08-19T06:55:00Z",
        ),
        compatibility_vector=TransitionCompatibility(
            tempo_fit=0.9,
            beat_grid_fit=0.8,
            phrase_fit=0.7,
            harmonic_fit=0.75,
            groove_continuity=0.85,
            structural_fit=0.8,
            timbral_fit=0.65,
            melodic_fit=0.6,
            semantic_fit=0.7,
        ),
        risk_vector=TransitionRisk(
            bass_collision=0.15,
            vocal_collision=0.1,
            spectral_masking=0.2,
            loudness_discontinuity=0.1,
            harmonic_clash=0.2,
            phrase_mismatch=0.15,
            tempo_instability=0.05,
            transient_overload=0.1,
            uncertainty=0.2,
        ),
        cost_vector=TransitionCost(
            tempo_change_percent=1.5,
            time_stretch_cost=0.1,
            pitch_shift_semitones=0.0,
            key_shift_cost=0.0,
            loop_dependency=False,
            stem_dependency=False,
            effect_dependency=False,
            preparation_complexity=0.2,
        ),
        energy_effect=TransitionEnergyEffect(
            source_energy_state=0.55,
            target_energy_state=0.65,
            delta=0.1,
            local_curve_alignment=0.9,
            direction=EnergyDirection.RISE,
            confidence=confidence,
        ),
        candidate_strategies=(
            TransitionStrategyCandidate(
                strategy=TransitionStrategy.EQ_BLEND,
                suitability=0.88,
                required_capabilities=("eq",),
                explanation_codes=("tempo_fit", "phrase_fit"),
            ),
            TransitionStrategyCandidate(
                strategy=TransitionStrategy.SHORT_BLEND,
                suitability=0.72,
                required_capabilities=("channel_faders",),
                explanation_codes=("low_risk",),
            ),
        ),
        preferred_strategy=TransitionStrategy.EQ_BLEND,
        usable_window=TransitionWindow(
            source_start_seconds=120.0,
            source_end_seconds=136.0,
            target_start_seconds=0.0,
            target_end_seconds=16.0,
            source_bar_count=8,
            target_bar_count=8,
            confidence=confidence,
        ),
        contextual_projection=ContextualTransitionProjection(
            context_id=context_id,
            context_version=context_version,
            score=0.86,
            blocked_reasons=(),
            rank_features=("tempo_fit", "energy_rise"),
            confidence=confidence,
            explanation_codes=("good_fit",),
        ),
        confidence=confidence,
        explanations=(
            TransitionExplanation(
                code="good_fit",
                severity="info",
                dimension="overall",
                evidence_refs=("ev_a", "ev_b"),
                confidence=confidence,
            ),
        ),
        evidence_refs=("ev_a", "ev_b"),
        warnings=("review_phrase_boundary",),
    )


def test_inspector_returns_explicit_missing_without_recompute(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    revision = _revision()
    ledger = PlaylistRevisionRepository()
    before = ledger.count_revisions(str(revision["playlist_id"]))

    result = DesktopTransitionInspectorTransport().inspect(
        revision_id=str(revision["revision_id"]),
        pair_index=0,
    )

    assert result["schema"] == "applaylist-desktop-transition-inspection-r1"
    assert result["state"] == "missing"
    assert result["selected_snapshot_id"] is None
    assert result["assessment"] is None
    assert result["source"]["track_id"] == "trk_a"
    assert result["target"]["track_id"] == "trk_b"
    assert result["available_snapshots"] == ()
    assert result["transition_recomputation_authorized"] is False
    assert result["playlist_mutation_authorized"] is False
    assert ledger.count_revisions(str(revision["playlist_id"])) == before


def test_inspector_projects_persisted_assessment_for_revision_adjacent_pair(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    revision = _revision()
    repository = MusicIntelligenceRepository()
    snapshot_id = repository.append_transition_assessment(_assessment())

    result = DesktopTransitionInspectorTransport().inspect(
        revision_id=str(revision["revision_id"]),
        pair_index=0,
    )

    assert result["state"] == "present"
    assert result["selected_snapshot_id"] == snapshot_id
    assert len(result["available_snapshots"]) == 1
    assessment = result["assessment"]
    assert assessment["transition_id"] == "trn_a_b"
    assert assessment["preferred_strategy"] == "eq_blend"
    assert assessment["compatibility"]["tempo_fit"] == 0.9
    assert assessment["risk"]["uncertainty"] == 0.2
    assert assessment["energy_effect"]["direction"] == "rise"
    assert assessment["contextual_projection"]["score"] == 0.86
    assert assessment["evidence_refs"] == ["ev_a", "ev_b"]
    encoded = json.dumps(result, sort_keys=True)
    assert "payload_json" not in encoded
    assert "content_utf8" not in encoded
    assert "/Users/" not in encoded


def test_inspector_rejects_nonexistent_pair_index_and_never_accepts_renderer_track_ids(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    revision = _revision()

    with pytest.raises(DesktopTransitionInspectorError) as exc_info:
        DesktopTransitionInspectorTransport().inspect(
            revision_id=str(revision["revision_id"]),
            pair_index=2,
        )
    assert exc_info.value.code == "invalid_transition_inspection_request"


def test_inspector_detects_persisted_snapshot_integrity_tamper(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_database(monkeypatch, tmp_path)
    revision = _revision()
    repository = MusicIntelligenceRepository()
    snapshot_id = repository.append_transition_assessment(_assessment())
    with get_sqlite_connection() as conn:
        conn.execute(
            "UPDATE transition_assessment_snapshots SET payload_json=? WHERE snapshot_id=?",
            ('{"tampered":true}', snapshot_id),
        )
        conn.commit()

    with pytest.raises(RuntimeError, match="integrity"):
        DesktopTransitionInspectorTransport().inspect(
            revision_id=str(revision["revision_id"]),
            pair_index=0,
        )


def test_authenticated_transition_inspector_route_is_strict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = _configure_database(monkeypatch, tmp_path)
    revision = _revision()
    MusicIntelligenceRepository().append_transition_assessment(_assessment())
    process, ready = _start_extended_sidecar(database)
    body = json.dumps({"revision_id": revision["revision_id"], "pair_index": 0}).encode()
    try:
        status, payload = _request(
            ready,
            method="POST",
            path="/v1/playlist/transition/inspect",
            secret="X" * 48,
            body=body,
        )
        assert status == 401
        assert payload == {"error": "unauthorized"}

        status, payload = _request(
            ready,
            method="POST",
            path="/v1/playlist/transition/inspect",
            body=json.dumps(
                {"revision_id": revision["revision_id"], "pair_index": 0, "source_track_id": "trk_a"}
            ).encode(),
        )
        assert status == 400
        assert payload == {"error": "invalid_transition_inspection_request"}

        status, payload = _request(
            ready,
            method="POST",
            path="/v1/playlist/transition/inspect",
            body=body,
        )
        assert status == 200
        assert payload["state"] == "present"
        assert payload["source"]["track_id"] == "trk_a"
        assert payload["target"]["track_id"] == "trk_b"
        assert payload["transition_recomputation_authorized"] is False

        status, shutdown = _request(ready, method="POST", path="/v1/shutdown")
        assert status == 202
        assert shutdown == {"status": "shutting_down"}
        _finish(process)
    finally:
        if process.poll() is None:
            process.kill()
            _finish(process)
