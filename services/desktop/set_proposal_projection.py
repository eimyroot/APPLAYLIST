from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from core.intelligence.set_optimizer_contract import SetOptimizerResult

DESKTOP_SET_PROPOSAL_SCHEMA = "applaylist-desktop-set-proposal-r1"

_MAX_DISPLAY_NAME_CHARS = 512
_MAX_TOKEN_CHARS = 256
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,255}$")


class DesktopSetProposalProjectionError(ValueError):
    """Raised when optimizer evidence cannot be projected safely to the renderer."""


def _path_shaped_text(value: str) -> bool:
    return (
        value.startswith("/")
        or value.startswith("\\\\")
        or bool(re.match(r"^[A-Za-z]:[\\/]", value))
    )


def _safe_token(value: object, field_name: str, *, maximum: int = _MAX_TOKEN_CHARS) -> str:
    text = str(value)
    if (
        not text
        or text != text.strip()
        or len(text) > maximum
        or _SAFE_TOKEN_RE.fullmatch(text) is None
    ):
        raise DesktopSetProposalProjectionError(f"{field_name} is not renderer-safe")
    return text


def _safe_display_name(value: object, track_id: str) -> str:
    if not isinstance(value, str):
        raise DesktopSetProposalProjectionError(
            f"display name is missing for track {track_id}"
        )
    text = value.strip()
    if (
        not text
        or len(text) > _MAX_DISPLAY_NAME_CHARS
        or any(ord(character) < 32 or ord(character) == 127 for character in text)
        or _path_shaped_text(text)
    ):
        raise DesktopSetProposalProjectionError(
            f"display name is not renderer-safe for track {track_id}"
        )
    return text


def _safe_codes(values: tuple[str, ...], field_name: str) -> list[str]:
    return [_safe_token(value, field_name, maximum=128) for value in values]


def _alternative_payload(
    alternative: Any,
    *,
    display_name_by_track_id: Mapping[str, str],
) -> dict[str, object]:
    sequence: list[dict[str, object]] = []
    for step in alternative.resulting_state.selected_steps:
        track_id = _safe_token(step.track_id, "track_id")
        if track_id not in display_name_by_track_id:
            raise DesktopSetProposalProjectionError(
                f"display name is missing for track {track_id}"
            )
        sequence.append(
            {
                "order_index": int(step.order_index),
                "track_id": track_id,
                "display_name": _safe_display_name(
                    display_name_by_track_id[track_id],
                    track_id,
                ),
                "phase_id": _safe_token(step.phase_id, "phase_id"),
            }
        )

    transition_ids = [
        _safe_token(value, "transition_id") for value in alternative.transition_ids
    ]
    candidate_scores = [float(value) for value in alternative.candidate_scores]
    if len(transition_ids) != len(candidate_scores):
        raise DesktopSetProposalProjectionError(
            "transition ids and candidate scores are inconsistent"
        )

    objective = alternative.objective
    return {
        "path_id": _safe_token(alternative.path_id, "path_id"),
        "rank": int(alternative.rank),
        "sequence": sequence,
        "transition_ids": transition_ids,
        "candidate_scores": candidate_scores,
        "objective": {
            "depth": int(objective.depth),
            "mean_candidate_score": float(objective.mean_candidate_score),
            "minimum_candidate_score": float(objective.minimum_candidate_score),
            "required_track_completion": float(objective.required_track_completion),
            "remaining_required_count": int(objective.remaining_required_count),
            "target_reached": bool(objective.target_reached),
        },
        "explanation_codes": _safe_codes(
            tuple(alternative.explanation_codes),
            "alternative_explanation_code",
        ),
    }


def project_set_optimizer_result(
    *,
    result: SetOptimizerResult,
    display_name_by_track_id: Mapping[str, str],
) -> dict[str, object]:
    """Project immutable optimizer evidence into a renderer-safe desktop DTO.

    The projection is intentionally lossy. It excludes filesystem paths, provider
    internals, evidence refs, optimizer/input fingerprints, and raw domain objects.
    """

    if not isinstance(display_name_by_track_id, Mapping):
        raise DesktopSetProposalProjectionError(
            "display_name_by_track_id must be a mapping"
        )

    alternatives = [
        _alternative_payload(
            alternative,
            display_name_by_track_id=display_name_by_track_id,
        )
        for alternative in result.alternatives
    ]

    if [item["rank"] for item in alternatives] != list(
        range(1, len(alternatives) + 1)
    ):
        raise DesktopSetProposalProjectionError(
            "optimizer alternatives are not contiguous by rank"
        )

    return {
        "schema": DESKTOP_SET_PROPOSAL_SCHEMA,
        "proposal_id": _safe_token(result.result_id, "result_id"),
        "status": _safe_token(result.status.value, "status", maximum=64),
        "alternatives": alternatives,
        "reason_codes": _safe_codes(
            tuple(result.explanation_codes),
            "result_explanation_code",
        ),
        "warning_codes": _safe_codes(
            tuple(result.warnings),
            "result_warning_code",
        ),
        "budget_exhausted": bool(result.budget_exhausted),
        "missing_evidence_detected": bool(result.missing_evidence_detected),
        "deterministic_ordering": bool(result.deterministic_ordering),
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
    }


__all__ = [
    "DESKTOP_SET_PROPOSAL_SCHEMA",
    "DesktopSetProposalProjectionError",
    "project_set_optimizer_result",
]
