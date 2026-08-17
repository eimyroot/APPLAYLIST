from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

CURATED_REAL_LIBRARY_BENCHMARK_VERSION = "curated-real-library-benchmark-r1"
HUMAN_DJ_REVIEW_PROTOCOL_VERSION = "human-dj-review-r1"


def _non_empty(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _unit(value: float, field_name: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return numeric


def _score(value: float, field_name: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric) or not 1.0 <= numeric <= 5.0:
        raise ValueError(f"{field_name} must be between 1 and 5")
    return numeric


def _ref(value: tuple[str, str], field_name: str) -> tuple[str, str]:
    if len(value) != 2:
        raise ValueError(f"{field_name} must contain exactly two values")
    return (_non_empty(value[0], f"{field_name}[0]"), _non_empty(value[1], f"{field_name}[1]"))


class CuratedSetRole(StrEnum):
    OPENING = "opening"
    BUILD = "build"
    MID_SET = "mid_set"
    PEAK = "peak"
    RESET = "reset"
    CLOSING = "closing"


REQUIRED_CURATED_SET_ROLES_R1 = tuple(CuratedSetRole)


class ReviewPlanStrategy(StrEnum):
    GREEDY_RECOMMEND_NEXT = "greedy_recommend_next"
    BOUNDED_BEAM = "bounded_beam"


class HumanPlanPreference(StrEnum):
    PLAN_A = "plan_a"
    PLAN_B = "plan_b"
    TIE = "tie"
    ABSTAIN = "abstain"


class HumanReviewDimension(StrEnum):
    TRANSITION_SMOOTHNESS = "transition_smoothness"
    PHRASE_ALIGNMENT = "phrase_alignment"
    ENERGY_FLOW = "energy_flow"
    DRAMATURGICAL_FIT = "dramaturgical_fit"
    SET_COHERENCE = "set_coherence"
    ALTERNATIVE_USEFULNESS = "alternative_usefulness"


REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1 = tuple(HumanReviewDimension)


class HumanReviewProtocolVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class CuratedLibrarySnapshot:
    snapshot_id: str
    snapshot_version: str
    library_fingerprint: str
    track_ids: tuple[str, ...]
    generated_at: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", _non_empty(self.snapshot_id, "snapshot_id"))
        object.__setattr__(
            self,
            "snapshot_version",
            _non_empty(self.snapshot_version, "snapshot_version"),
        )
        object.__setattr__(
            self,
            "library_fingerprint",
            _non_empty(self.library_fingerprint, "library_fingerprint"),
        )
        tracks = tuple(_non_empty(item, "track_id") for item in self.track_ids)
        if len(tracks) < 2:
            raise ValueError("curated library snapshot must contain at least two tracks")
        if len(set(tracks)) != len(tracks):
            raise ValueError("curated library snapshot track_ids must be unique")
        object.__setattr__(self, "track_ids", tracks)
        object.__setattr__(self, "generated_at", _non_empty(self.generated_at, "generated_at"))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class ReviewableSetPlan:
    plan_id: str
    strategy: ReviewPlanStrategy
    result_id: str
    path_id: str
    ordered_track_ids: tuple[str, ...]
    transition_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", _non_empty(self.plan_id, "plan_id"))
        object.__setattr__(self, "result_id", _non_empty(self.result_id, "result_id"))
        object.__setattr__(self, "path_id", _non_empty(self.path_id, "path_id"))
        tracks = tuple(_non_empty(item, "ordered_track_id") for item in self.ordered_track_ids)
        if not tracks:
            raise ValueError("ordered_track_ids must not be empty")
        object.__setattr__(self, "ordered_track_ids", tracks)
        object.__setattr__(
            self,
            "transition_ids",
            tuple(_non_empty(item, "transition_id") for item in self.transition_ids),
        )
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class CuratedReviewCase:
    case_id: str
    snapshot_ref: tuple[str, str]
    scenario_fingerprint: str
    set_role: CuratedSetRole
    benchmark_ref: tuple[str, str]
    greedy_plan: ReviewableSetPlan
    beam_plan: ReviewableSetPlan
    engineering_acceptance_passed: bool
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", _non_empty(self.case_id, "case_id"))
        object.__setattr__(self, "snapshot_ref", _ref(self.snapshot_ref, "snapshot_ref"))
        object.__setattr__(
            self,
            "scenario_fingerprint",
            _non_empty(self.scenario_fingerprint, "scenario_fingerprint"),
        )
        object.__setattr__(self, "benchmark_ref", _ref(self.benchmark_ref, "benchmark_ref"))
        if self.greedy_plan.strategy is not ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT:
            raise ValueError("greedy_plan must use greedy_recommend_next strategy")
        if self.beam_plan.strategy is not ReviewPlanStrategy.BOUNDED_BEAM:
            raise ValueError("beam_plan must use bounded_beam strategy")
        if self.greedy_plan.plan_id == self.beam_plan.plan_id:
            raise ValueError("greedy and beam plans must have distinct plan ids")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class BlindedPlanAssignment:
    assignment_id: str
    case_id: str
    slot_a_plan_id: str
    slot_b_plan_id: str
    assignment_fingerprint: str
    algorithm_identity_hidden: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignment_id", _non_empty(self.assignment_id, "assignment_id"))
        object.__setattr__(self, "case_id", _non_empty(self.case_id, "case_id"))
        object.__setattr__(
            self,
            "slot_a_plan_id",
            _non_empty(self.slot_a_plan_id, "slot_a_plan_id"),
        )
        object.__setattr__(
            self,
            "slot_b_plan_id",
            _non_empty(self.slot_b_plan_id, "slot_b_plan_id"),
        )
        if self.slot_a_plan_id == self.slot_b_plan_id:
            raise ValueError("blind assignment slots must reference distinct plans")
        object.__setattr__(
            self,
            "assignment_fingerprint",
            _non_empty(self.assignment_fingerprint, "assignment_fingerprint"),
        )
        if not self.algorithm_identity_hidden:
            raise ValueError("human review R1 requires algorithm identity to remain hidden")


@dataclass(frozen=True, slots=True)
class HumanDimensionPairRating:
    dimension: HumanReviewDimension
    plan_a_score: float
    plan_b_score: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_a_score", _score(self.plan_a_score, "plan_a_score"))
        object.__setattr__(self, "plan_b_score", _score(self.plan_b_score, "plan_b_score"))


@dataclass(frozen=True, slots=True)
class HumanDJReview:
    review_id: str
    assignment_id: str
    reviewer_ref: str
    preference: HumanPlanPreference
    ratings: tuple[HumanDimensionPairRating, ...]
    confidence: float
    observed_at: str
    algorithm_identity_was_hidden: bool = True
    reason_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "review_id", _non_empty(self.review_id, "review_id"))
        object.__setattr__(self, "assignment_id", _non_empty(self.assignment_id, "assignment_id"))
        object.__setattr__(self, "reviewer_ref", _non_empty(self.reviewer_ref, "reviewer_ref"))
        ratings = tuple(self.ratings)
        dimensions = tuple(item.dimension for item in ratings)
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("human review dimensions must be unique")
        object.__setattr__(self, "ratings", ratings)
        object.__setattr__(self, "confidence", _unit(self.confidence, "confidence"))
        object.__setattr__(self, "observed_at", _non_empty(self.observed_at, "observed_at"))
        if not self.algorithm_identity_was_hidden:
            raise ValueError("review is invalid when algorithm identity was visible")
        if self.activation_authorized:
            raise ValueError("human review R1 cannot authorize optimizer activation")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class HumanReviewProtocolThresholds:
    policy_id: str = "curated-real-library-human-review-acceptance"
    policy_version: str = HUMAN_DJ_REVIEW_PROTOCOL_VERSION
    minimum_cases: int = 12
    minimum_reviews_per_case: int = 1
    required_set_roles: tuple[CuratedSetRole, ...] = REQUIRED_CURATED_SET_ROLES_R1
    minimum_reviewed_case_fraction: float = 1.0
    minimum_blind_integrity_rate: float = 1.0
    minimum_dimension_coverage_rate: float = 1.0
    maximum_engineering_regressions: int = 0
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _non_empty(self.policy_id, "policy_id"))
        object.__setattr__(
            self,
            "policy_version",
            _non_empty(self.policy_version, "policy_version"),
        )
        if self.minimum_cases <= 0 or self.minimum_reviews_per_case <= 0:
            raise ValueError("minimum case and review counts must be positive")
        roles = tuple(self.required_set_roles)
        if not roles or len(set(roles)) != len(roles):
            raise ValueError("required_set_roles must be non-empty and unique")
        object.__setattr__(self, "required_set_roles", roles)
        for field_name in (
            "minimum_reviewed_case_fraction",
            "minimum_blind_integrity_rate",
            "minimum_dimension_coverage_rate",
        ):
            object.__setattr__(self, field_name, _unit(getattr(self, field_name), field_name))
        if self.maximum_engineering_regressions < 0:
            raise ValueError("maximum_engineering_regressions must be non-negative")
        if self.activation_authorized:
            raise ValueError("human review thresholds cannot authorize activation")


@dataclass(frozen=True, slots=True)
class DimensionReviewEvidence:
    dimension: HumanReviewDimension
    sample_count: int
    greedy_mean: float
    beam_mean: float
    beam_minus_greedy: float

    def __post_init__(self) -> None:
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        object.__setattr__(self, "greedy_mean", _score(self.greedy_mean, "greedy_mean"))
        object.__setattr__(self, "beam_mean", _score(self.beam_mean, "beam_mean"))
        delta = float(self.beam_minus_greedy)
        if not math.isfinite(delta) or not -4.0 <= delta <= 4.0:
            raise ValueError("beam_minus_greedy must be between -4 and 4")
        object.__setattr__(self, "beam_minus_greedy", delta)


@dataclass(frozen=True, slots=True)
class CuratedRealLibraryHumanReviewReport:
    report_id: str
    snapshot_ref: tuple[str, str]
    protocol_ref: tuple[str, str]
    case_count: int
    reviewed_case_count: int
    review_count: int
    covered_set_roles: tuple[CuratedSetRole, ...]
    missing_set_roles: tuple[CuratedSetRole, ...]
    reviewed_case_fraction: float
    blind_integrity_rate: float
    dimension_coverage_rate: float
    engineering_regression_count: int
    greedy_preference_count: int
    beam_preference_count: int
    tie_count: int
    abstain_count: int
    dimension_evidence: tuple[DimensionReviewEvidence, ...]
    verdict: HumanReviewProtocolVerdict
    activation_authorized: bool = False
    explanation_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", _non_empty(self.report_id, "report_id"))
        object.__setattr__(self, "snapshot_ref", _ref(self.snapshot_ref, "snapshot_ref"))
        object.__setattr__(self, "protocol_ref", _ref(self.protocol_ref, "protocol_ref"))
        for field_name in (
            "case_count",
            "reviewed_case_count",
            "review_count",
            "engineering_regression_count",
            "greedy_preference_count",
            "beam_preference_count",
            "tie_count",
            "abstain_count",
        ):
            value = int(getattr(self, field_name))
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
            object.__setattr__(self, field_name, value)
        if self.reviewed_case_count > self.case_count:
            raise ValueError("reviewed_case_count cannot exceed case_count")
        if (
            self.greedy_preference_count
            + self.beam_preference_count
            + self.tie_count
            + self.abstain_count
            != self.review_count
        ):
            raise ValueError("preference counts must equal review_count")
        for field_name in (
            "reviewed_case_fraction",
            "blind_integrity_rate",
            "dimension_coverage_rate",
        ):
            object.__setattr__(self, field_name, _unit(getattr(self, field_name), field_name))
        object.__setattr__(self, "covered_set_roles", tuple(self.covered_set_roles))
        object.__setattr__(self, "missing_set_roles", tuple(self.missing_set_roles))
        object.__setattr__(self, "dimension_evidence", tuple(self.dimension_evidence))
        if self.activation_authorized:
            raise ValueError("human review report cannot authorize optimizer activation")
        object.__setattr__(self, "explanation_codes", tuple(self.explanation_codes))


__all__ = [
    "CURATED_REAL_LIBRARY_BENCHMARK_VERSION",
    "HUMAN_DJ_REVIEW_PROTOCOL_VERSION",
    "REQUIRED_CURATED_SET_ROLES_R1",
    "REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1",
    "BlindedPlanAssignment",
    "CuratedLibrarySnapshot",
    "CuratedRealLibraryHumanReviewReport",
    "CuratedReviewCase",
    "CuratedSetRole",
    "DimensionReviewEvidence",
    "HumanDJReview",
    "HumanDimensionPairRating",
    "HumanPlanPreference",
    "HumanReviewDimension",
    "HumanReviewProtocolThresholds",
    "HumanReviewProtocolVerdict",
    "ReviewPlanStrategy",
    "ReviewableSetPlan",
]
