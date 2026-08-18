from __future__ import annotations

import json

import pytest

from core.intelligence.set_contract import SequenceState, SetStep
from core.intelligence.set_optimizer_contract import (
    SetOptimizerResult,
    SetOptimizerStatus,
    SetPathAlternative,
    SetPathObjective,
)
from services.desktop.set_proposal_projection import (
    DESKTOP_SET_PROPOSAL_SCHEMA,
    DesktopSetProposalProjectionError,
    project_set_optimizer_result,
)


def _state(track_ids: tuple[str, ...]) -> SequenceState:
    steps = tuple(
        SetStep(
            order_index=index,
            track_id=track_id,
            segment_id=f"{track_id}:whole",
            phase_id="phase:main",
        )
        for index, track_id in enumerate(track_ids)
    )
    return SequenceState(
        state_id="state:proposal",
        state_version="set-intelligence-v1",
        selected_steps=steps,
        current_track_id=steps[-1].track_id,
        current_segment_id=steps[-1].segment_id,
        used_track_ids=track_ids,
        cumulative_duration_seconds=900.0,
        current_energy_state=0.72,
        warnings=("private-state-warning",),
        evidence_refs=("evidence:private",),
    )


def _alternative(
    *,
    rank: int,
    path_id: str,
    track_ids: tuple[str, ...],
    explanation_codes: tuple[str, ...] = ("path_complete",),
) -> SetPathAlternative:
    state = _state(track_ids)
    added_steps = state.selected_steps[1:]
    transition_ids = tuple(
        f"transition:{rank}:{index}"
        for index in range(1, len(added_steps) + 1)
    )
    candidate_scores = tuple(
        0.75 + 0.01 * index for index in range(len(added_steps))
    )
    return SetPathAlternative(
        path_id=path_id,
        rank=rank,
        added_steps=added_steps,
        resulting_state=state,
        transition_ids=transition_ids,
        candidate_scores=candidate_scores,
        objective=SetPathObjective(
            depth=len(added_steps),
            mean_candidate_score=sum(candidate_scores) / len(candidate_scores),
            minimum_candidate_score=min(candidate_scores),
            required_track_completion=1.0,
            remaining_required_count=0,
            target_reached=True,
        ),
        explanation_codes=explanation_codes,
        evidence_refs=("evidence:must-not-leak",),
    )


def _successful_result(
    *,
    warnings: tuple[str, ...] = ("bounded_search_complete",),
    explanation_codes: tuple[str, ...] = ("target_reached",),
) -> SetOptimizerResult:
    return SetOptimizerResult(
        result_id="setresult:desktop:r1",
        input_fingerprint="sha256:private-input-fingerprint",
        optimizer_ref=("bounded-beam-lookahead", "v1"),
        intent_ref=("intent:private", "v1"),
        root_state_ref=("state:private", "v1"),
        base_transition_context_ref=("transition-context:private", "v1"),
        status=SetOptimizerStatus.TARGET_REACHED,
        alternatives=(
            _alternative(
                rank=1,
                path_id="path:one",
                track_ids=("track:a", "track:b", "track:c"),
            ),
            _alternative(
                rank=2,
                path_id="path:two",
                track_ids=("track:a", "track:d", "track:e"),
            ),
        ),
        deepest_depth=2,
        expanded_candidates=42,
        beam_pruned_candidates=7,
        budget_exhausted=False,
        missing_evidence_detected=False,
        deterministic_ordering=True,
        explanation_codes=explanation_codes,
        warnings=warnings,
    )


def _display_names() -> dict[str, str]:
    return {
        "track:a": "Artist A — Track A",
        "track:b": "Artist B — Track B",
        "track:c": "Artist C — Track C",
        "track:d": "Artist D — Track D",
        "track:e": "Artist E — Track E",
    }


def test_projects_renderer_safe_ranked_alternatives() -> None:
    payload = project_set_optimizer_result(
        result=_successful_result(),
        display_name_by_track_id=_display_names(),
    )

    assert payload["schema"] == DESKTOP_SET_PROPOSAL_SCHEMA
    assert payload["status"] == "target_reached"
    assert [item["rank"] for item in payload["alternatives"]] == [1, 2]
    assert payload["alternatives"][0]["sequence"][0] == {
        "order_index": 0,
        "track_id": "track:a",
        "display_name": "Artist A — Track A",
        "phase_id": "phase:main",
    }
    assert payload["activation_authorized"] is False
    assert payload["personal_dj_model_training_authorized"] is False


def test_projection_is_deterministic_for_mapping_order() -> None:
    names = _display_names()
    reversed_names = dict(reversed(tuple(names.items())))

    first = project_set_optimizer_result(
        result=_successful_result(),
        display_name_by_track_id=names,
    )
    second = project_set_optimizer_result(
        result=_successful_result(),
        display_name_by_track_id=reversed_names,
    )

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_private_domain_fields_do_not_reach_renderer_payload() -> None:
    payload = project_set_optimizer_result(
        result=_successful_result(),
        display_name_by_track_id=_display_names(),
    )
    encoded = json.dumps(payload, sort_keys=True).lower()

    for forbidden_key in (
        "input_fingerprint",
        "optimizer_ref",
        "intent_ref",
        "root_state_ref",
        "base_transition_context_ref",
        "evidence_refs",
        "provider",
        "absolute_path",
    ):
        assert forbidden_key not in encoded


def test_missing_display_name_fails_closed() -> None:
    names = _display_names()
    names.pop("track:c")

    with pytest.raises(
        DesktopSetProposalProjectionError,
        match="display name is missing",
    ):
        project_set_optimizer_result(
            result=_successful_result(),
            display_name_by_track_id=names,
        )


@pytest.mark.parametrize(
    "unsafe_name",
    (
        "/Users/example/Music/secret.mp3",
        r"\\server\share\secret.mp3",
        "C:\\Music\\secret.mp3",
        "unsafe\nname",
    ),
)
def test_path_or_control_shaped_display_name_fails_closed(unsafe_name: str) -> None:
    names = _display_names()
    names["track:a"] = unsafe_name

    with pytest.raises(
        DesktopSetProposalProjectionError,
        match="display name is not renderer-safe",
    ):
        project_set_optimizer_result(
            result=_successful_result(),
            display_name_by_track_id=names,
        )


def test_unsafe_result_warning_code_fails_closed() -> None:
    with pytest.raises(
        DesktopSetProposalProjectionError,
        match="result_warning_code is not renderer-safe",
    ):
        project_set_optimizer_result(
            result=_successful_result(warnings=("/private/path/leak",)),
            display_name_by_track_id=_display_names(),
        )


def test_no_eligible_path_projects_without_track_labels() -> None:
    result = SetOptimizerResult(
        result_id="setresult:none",
        input_fingerprint="sha256:private",
        optimizer_ref=("bounded-beam-lookahead", "v1"),
        intent_ref=("intent:none", "v1"),
        root_state_ref=("state:none", "v1"),
        base_transition_context_ref=("transition-context:none", "v1"),
        status=SetOptimizerStatus.NO_ELIGIBLE_PATH,
        alternatives=(),
        deepest_depth=0,
        expanded_candidates=3,
        beam_pruned_candidates=0,
        budget_exhausted=False,
        missing_evidence_detected=False,
        deterministic_ordering=True,
        explanation_codes=("no_eligible_path",),
        warnings=(),
    )

    payload = project_set_optimizer_result(
        result=result,
        display_name_by_track_id={},
    )

    assert payload["status"] == "no_eligible_path"
    assert payload["alternatives"] == []
    assert payload["reason_codes"] == ["no_eligible_path"]
