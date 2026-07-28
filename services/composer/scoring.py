from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.harmonic import camelot_compatible
from core.transition.contracts import TransitionProfile
from services.intelligence.fusion import fuse_signals
from services.transition.assessment_service import assess_pair


def score_transition(
    a: Any,
    b: Any,
    *,
    external_features: Mapping[str, Any] | None = None,
) -> float:
    """Deterministic legacy-compatible transition score on an approximate 0-3 scale.

    External intelligence is accepted only as explicit caller-owned input.
    The scorer never performs network access and never generates random data.
    """

    score = 0.0

    if getattr(a, "bpm", None) is not None and getattr(b, "bpm", None) is not None:
        diff = abs(float(a.bpm) - float(b.bpm))
        score += max(0.0, 1.0 - diff / 10.0)

    if camelot_compatible(
        getattr(a, "camelot", None),
        getattr(b, "camelot", None),
    ):
        score += 1.0

    if getattr(a, "energy", None) is not None and getattr(b, "energy", None) is not None:
        score += max(0.0, 1.0 - abs(float(a.energy) - float(b.energy)))

    if external_features:
        score += fuse_signals(b, dict(external_features))

    return float(score)


def score_transition_intelligence(
    a: Any,
    b: Any,
    *,
    profile: TransitionProfile | str = TransitionProfile.BALANCED,
) -> float:
    """Return the explicit Transition Intelligence analysis score on a 0-100 scale.

    This score is not composer-ranking compatible and must remain shadow-only until
    a versioned composition policy normalizes all ranking contributions.
    """

    assessment = assess_pair(a, b, profile=profile)
    return assessment.analysis.overall_score
