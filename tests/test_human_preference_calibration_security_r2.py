from __future__ import annotations

import pytest

from core.intelligence.curated_real_library_review_contract import (
    HumanDJReview,
    HumanDimensionPairRating,
    HumanPlanPreference,
    HumanReviewDimension,
)
from services.intelligence.human_preference_calibration import (
    HumanPreferenceCalibrationError,
    _validate_complete_human_review,
)


def test_incomplete_bundle63_review_is_rejected_for_calibration() -> None:
    incomplete = HumanDJReview(
        review_id="review:incomplete",
        assignment_id="assignment:incomplete",
        reviewer_ref="synthetic-test-reviewer",
        preference=HumanPlanPreference.TIE,
        ratings=(
            HumanDimensionPairRating(
                dimension=HumanReviewDimension.SET_COHERENCE,
                plan_a_score=4.0,
                plan_b_score=4.0,
            ),
        ),
        confidence=0.9,
        observed_at="2026-08-23T03:00:00Z",
        algorithm_identity_was_hidden=True,
        reason_codes=("synthetic_test_fixture_only",),
        evidence_refs=("evidence:synthetic-incomplete",),
        activation_authorized=False,
    )

    with pytest.raises(HumanPreferenceCalibrationError, match="all Bundle 63"):
        _validate_complete_human_review(incomplete)
