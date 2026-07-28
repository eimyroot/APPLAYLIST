from __future__ import annotations

from typing import Any

from core.transition.contracts import TransitionAssessment, TransitionProfile
from core.transition.engine import assess_transition


def assess_pair(
    track_a: Any,
    track_b: Any,
    *,
    profile: TransitionProfile | str = TransitionProfile.BALANCED,
) -> TransitionAssessment:
    resolved = profile if isinstance(profile, TransitionProfile) else TransitionProfile(profile)
    return assess_transition(track_a, track_b, profile=resolved)
