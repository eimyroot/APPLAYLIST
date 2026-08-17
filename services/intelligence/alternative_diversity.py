from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace

from core.intelligence.set_optimizer_contract import SetOptimizerResult, SetPathAlternative
from core.intelligence.set_optimizer_evaluation_contract import (
    AlternativeDiversityDecision,
    AlternativeDiversityPolicy,
    SetAlternativeSelection,
)


def _track_ids(alternative: SetPathAlternative) -> tuple[str, ...]:
    return tuple(step.track_id for step in alternative.added_steps)


def _track_jaccard(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    if not union:
        return 1.0
    return len(left_set & right_set) / len(union)


def _shared_prefix_fraction(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    denominator = min(len(left), len(right))
    if denominator == 0:
        return 1.0
    shared = 0
    for left_item, right_item in zip(left, right, strict=False):
        if left_item != right_item:
            break
        shared += 1
    return shared / denominator


def _differing_positions(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    shared_length = min(len(left), len(right))
    differences = sum(
        1
        for index in range(shared_length)
        if left[index] != right[index]
    )
    return differences + abs(len(left) - len(right))


def _similarity(
    candidate: SetPathAlternative,
    selected: SetPathAlternative,
) -> tuple[float, float, int]:
    candidate_tracks = _track_ids(candidate)
    selected_tracks = _track_ids(selected)
    return (
        _track_jaccard(candidate_tracks, selected_tracks),
        _shared_prefix_fraction(candidate_tracks, selected_tracks),
        _differing_positions(candidate_tracks, selected_tracks),
    )


def _reason_codes(
    *,
    jaccard: float,
    prefix: float,
    differing: int,
    policy: AlternativeDiversityPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if jaccard > policy.max_track_jaccard:
        reasons.append("track_jaccard_above_policy")
    if prefix > policy.max_shared_prefix_fraction:
        reasons.append("shared_prefix_above_policy")
    if differing < policy.minimum_differing_positions:
        reasons.append("insufficient_differing_positions")
    return tuple(reasons)


def _decision_against_selected(
    *,
    candidate: SetPathAlternative,
    selected: tuple[SetPathAlternative, ...],
    policy: AlternativeDiversityPolicy,
) -> AlternativeDiversityDecision:
    if not selected:
        return AlternativeDiversityDecision(
            path_id=candidate.path_id,
            source_rank=candidate.rank,
            selected=True,
            reason_codes=("highest_ranked_path_preserved",),
        )

    comparisons: list[tuple[int, float, float, int, str, tuple[str, ...]]] = []
    for existing in selected:
        jaccard, prefix, differing = _similarity(candidate, existing)
        reasons = _reason_codes(
            jaccard=jaccard,
            prefix=prefix,
            differing=differing,
            policy=policy,
        )
        comparisons.append(
            (len(reasons), jaccard, prefix, differing, existing.path_id, reasons)
        )

    violations = [item for item in comparisons if item[0] > 0]
    binding_pool = violations if violations else comparisons
    # Binding path is deterministic: most violated thresholds first, then greatest
    # overlap/prefix, then fewest differing positions, then stable path identity.
    binding_pool.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3], item[4]))
    _, jaccard, prefix, differing, nearest_path_id, binding_reasons = binding_pool[0]

    aggregate_reasons: list[str] = []
    for comparison in violations:
        for reason in comparison[5]:
            if reason not in aggregate_reasons:
                aggregate_reasons.append(reason)

    selected_candidate = not violations
    return AlternativeDiversityDecision(
        path_id=candidate.path_id,
        source_rank=candidate.rank,
        selected=selected_candidate,
        nearest_selected_path_id=nearest_path_id,
        track_jaccard=jaccard,
        shared_prefix_fraction=prefix,
        differing_positions=differing,
        reason_codes=(
            ("diversity_policy_pass",)
            if selected_candidate
            else tuple(aggregate_reasons or binding_reasons)
        ),
    )


def select_diverse_alternatives(
    *,
    result: SetOptimizerResult,
    policy: AlternativeDiversityPolicy,
) -> SetAlternativeSelection:
    """Select a deterministic diverse subset without changing optimizer truth.

    Source ranking is authoritative. Rank #1 is always preserved. Later alternatives
    are accepted only when they satisfy the explicit diversity policy relative to every
    already selected path. This is a post-search evidence selection layer; it does not
    modify candidate scores, path objectives, hard gates or TransitionAssessment data.
    """
    source = tuple(sorted(result.alternatives, key=lambda item: item.rank))
    selected: list[SetPathAlternative] = []
    decisions: list[AlternativeDiversityDecision] = []
    rejected: list[SetPathAlternative] = []

    for candidate in source:
        if len(selected) >= policy.alternative_limit:
            decisions.append(
                AlternativeDiversityDecision(
                    path_id=candidate.path_id,
                    source_rank=candidate.rank,
                    selected=False,
                    reason_codes=("alternative_limit_reached",),
                )
            )
            continue

        decision = _decision_against_selected(
            candidate=candidate,
            selected=tuple(selected),
            policy=policy,
        )
        decisions.append(decision)
        if decision.selected:
            selected.append(candidate)
        else:
            rejected.append(candidate)

    fallback_used = False
    if policy.allow_similarity_fallback and len(selected) < policy.alternative_limit:
        selected_ids = {item.path_id for item in selected}
        for candidate in rejected:
            if len(selected) >= policy.alternative_limit:
                break
            if candidate.path_id in selected_ids:
                continue
            selected.append(candidate)
            selected_ids.add(candidate.path_id)
            fallback_used = True
            for index, decision in enumerate(decisions):
                if decision.path_id == candidate.path_id:
                    decisions[index] = replace(
                        decision,
                        selected=True,
                        reason_codes=("similarity_fallback_selected",),
                    )
                    break

    reranked = tuple(
        replace(alternative, rank=index + 1)
        for index, alternative in enumerate(selected)
    )
    material = {
        "source_result_id": result.result_id,
        "source_input_fingerprint": result.input_fingerprint,
        "policy": asdict(policy),
        "selected_path_ids": [item.path_id for item in reranked],
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]
    return SetAlternativeSelection(
        selection_id=f"sas_{digest}",
        source_result_id=result.result_id,
        source_input_fingerprint=result.input_fingerprint,
        policy_ref=(policy.policy_id, policy.policy_version),
        selected_alternatives=reranked,
        decisions=tuple(decisions),
        requested_limit=policy.alternative_limit,
        similarity_fallback_used=fallback_used,
        deterministic_ordering=True,
    )


__all__ = ["select_diverse_alternatives"]
