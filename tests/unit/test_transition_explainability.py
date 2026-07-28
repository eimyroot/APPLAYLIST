from types import SimpleNamespace

import pytest

from services.composer.scoring import score_transition
from services.explainability.reasons import (
    explain_transition,
    explain_transition_intelligence,
)


def track(track_id: str, **overrides):
    values = {
        "track_id": track_id,
        "bpm": 128.0,
        "bpm_confidence": 0.9,
        "camelot": "8A",
        "key_confidence": 0.8,
        "energy": 0.5,
        "energy_confidence": 0.8,
        "percussive_ratio": 0.7,
        "percussive_confidence": 0.75,
        "harmonic_ratio": 0.4,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_legacy_explanation_matches_exact_composer_contributions() -> None:
    a = track("a")
    b = track("b", bpm=129.0, camelot="9A", energy=0.65)
    output = explain_transition(a, b, position=0.5)
    assert output["schema_version"] == "composer-explanation-v1"
    assert output["base_transition_score"] == pytest.approx(score_transition(a, b))
    assert output["ranking_score"] == pytest.approx(
        output["base_transition_score"] + output["energy_target_bonus"]
    )
    assert {reason["code"] for reason in output["reasons"]} >= {
        "bpm_delta",
        "harmonic_compatible",
        "energy_target_alignment",
    }


def test_transition_explanation_uses_analysis_contributions_and_links() -> None:
    a = track("a")
    b = track("b", bpm=129.0, camelot="9A", energy=0.65)
    output = explain_transition_intelligence(a, b)
    assert output["schema_version"] == "transition-explanation-v1"
    assert output["assessment_id"]
    assert output["analysis_id"]
    assert 0.0 <= output["transition_score"] <= 100.0
    assert 0.0 <= output["confidence"] <= 1.0
    assert output["classification"] in {"safe", "possible", "creative", "risky", "unknown"}
    assert all("contribution" in item for item in output["reasons"])
    assert output["recommended_overlap_beats"] is None
