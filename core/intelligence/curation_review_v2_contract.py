from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from core.intelligence.curated_real_library_review_contract import CuratedSetRole
from core.intelligence.human_preference_calibration_contract import CalibrationVerdict, ResolvedPreference

CURATION_REVIEW_PROTOCOL_VERSION = "curation-review-v2"
CURATION_CALIBRATION_VERSION = "curation-preference-calibration-v3"
HOLDOUT_VALIDATION_MANIFEST_VERSION = "holdout-validation-manifest-r1"
CURATION_AUDITION_MODE = "sequence_curation_only"


def _non_empty(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _unit(value: float | None, field_name: str) -> float | None:
    if value is None:
        return None
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
    return (
        _non_empty(value[0], f"{field_name}[0]"),
        _non_empty(value[1], f"{field_name}[1]"),
    )


class EvidenceRole(StrEnum):
    DEVELOPMENT_CALIBRATION = "development_calibration"
    HOLDOUT_VALIDATION = "holdout_validation"


class SelectionScope(StrEnum):
    REPRESENTATIVE_HOLDOUT = "representative_holdout"
    DIAGNOSTIC_CHALLENGE_SET = "diagnostic_challenge_set"


class EvaluationScope(StrEnum):
    PERSONAL_DJ_CALIBRATION = "personal_dj_calibration"
    MULTI_DJ_PRODUCT_EVALUATION = "multi_dj_product_evaluation"


class CurationReviewDimension(StrEnum):
    ENERGY_FLOW = "energy_flow"
    DRAMATURGICAL_FIT = "dramaturgical_fit"
    SET_COHERENCE = "set_coherence"
    ALTERNATIVE_USEFULNESS = "alternative_usefulness"
    TRACK_SELECTION_FIT = "track_selection_fit"


REQUIRED_CURATION_REVIEW_DIMENSIONS_V2 = tuple(CurationReviewDimension)


class CurationPreference(StrEnum):
    PLAN_A = "plan_a"
    PLAN_B = "plan_b"
    TIE = "tie"
    ABSTAIN = "abstain"


class HoldoutSystemOutcome(StrEnum):
    REVIEWABLE_PAIR = "reviewable_pair"
    TECHNICALLY_IDENTICAL_PAIR = "technically_identical_pair"
    NO_MEANINGFUL_ALTERNATIVE = "no_meaningful_alternative"
    MISSING_REQUIRED_EVIDENCE = "missing_required_evidence"
    SOURCE_GENERATION_FAILED = "source_generation_failed"
    CHALLENGER_NOT_PROVEN = "challenger_not_proven"


@dataclass(frozen=True, slots=True)
class CurationBlindAssignmentV2:
    assignment_id: str
    case_id: str
    reviewer_ref: str
    slot_a_plan_id: str
    slot_b_plan_id: str
    assignment_fingerprint: str
    algorithm_identity_hidden: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "assignment_id",
            "case_id",
            "reviewer_ref",
            "slot_a_plan_id",
            "slot_b_plan_id",
            "assignment_fingerprint",
        ):
            object.__setattr__(self, field_name, _non_empty(getattr(self, field_name), field_name))
        if self.slot_a_plan_id == self.slot_b_plan_id:
            raise ValueError("curation blind assignment slots must reference distinct plans")
        if not self.algorithm_identity_hidden:
            raise ValueError("curation review requires algorithm identity to remain hidden")


@dataclass(frozen=True, slots=True)
class CurationDimensionPairRating:
    dimension: CurationReviewDimension
    plan_a_score: float
    plan_b_score: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_a_score", _score(self.plan_a_score, "plan_a_score"))
        object.__setattr__(self, "plan_b_score", _score(self.plan_b_score, "plan_b_score"))


@dataclass(frozen=True, slots=True)
class CurationDJReviewV2:
    review_id: str
    assignment_id: str
    reviewer_ref: str
    evidence_role: EvidenceRole
    curation_packet_fingerprint: str
    source_blinded_packet_fingerprint: str
    preference: CurationPreference
    ratings: tuple[CurationDimensionPairRating, ...]
    confidence: float
    observed_at: str
    audition_mode: str = CURATION_AUDITION_MODE
    algorithm_identity_was_hidden: bool = True
    execution_quality_excluded_from_curation_judgment: bool = True
    reason_codes: tuple[str, ...] = ()
    notes: str = ""
    activation_authorized: bool = False
    personal_dj_model_training_authorized: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "review_id",
            "assignment_id",
            "reviewer_ref",
            "curation_packet_fingerprint",
            "source_blinded_packet_fingerprint",
            "observed_at",
        ):
            object.__setattr__(self, field_name, _non_empty(getattr(self, field_name), field_name))
        if self.audition_mode != CURATION_AUDITION_MODE:
            raise ValueError("curation review must use sequence_curation_only audition mode")
        if not self.algorithm_identity_was_hidden:
            raise ValueError("curation review is invalid when algorithm identity was visible")
        if not self.execution_quality_excluded_from_curation_judgment:
            raise ValueError("curation review must exclude live transition execution quality")
        ratings = tuple(self.ratings)
        dimensions = tuple(item.dimension for item in ratings)
        if len(dimensions) != len(REQUIRED_CURATION_REVIEW_DIMENSIONS_V2) or set(dimensions) != set(
            REQUIRED_CURATION_REVIEW_DIMENSIONS_V2
        ):
            raise ValueError("curation review requires all V2 dimensions exactly once")
        object.__setattr__(self, "ratings", ratings)
        object.__setattr__(self, "confidence", _unit(self.confidence, "confidence"))
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))
        object.__setattr__(self, "notes", str(self.notes))
        if self.activation_authorized:
            raise ValueError("curation review cannot authorize optimizer activation")
        if self.personal_dj_model_training_authorized:
            raise ValueError("curation review cannot authorize Personal DJ Model training")


@dataclass(frozen=True, slots=True)
class HoldoutValidationManifest:
    holdout_id: str
    holdout_version: str
    evidence_role: EvidenceRole
    selection_scope: SelectionScope
    source_snapshot_ref: tuple[str, str]
    case_selection_policy_ref: tuple[str, str]
    selection_seed_commitment: str
    selected_case_ids: tuple[str, ...]
    scenario_fingerprints: tuple[str, ...]
    required_set_roles: tuple[CuratedSetRole, ...]
    source_optimizer_sha: str
    challenger_sha: str
    challenger_policy_ref: tuple[str, str]
    challenger_config_digest: str
    calibration_policy_digest: str
    source_evidence_revisions: tuple[str, ...]
    generated_at: str
    human_labels_available_at_freeze: bool = False
    algorithm_identity_hidden: bool = True
    activation_authorized: bool = False
    personal_dj_model_training_authorized: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "holdout_id",
            "holdout_version",
            "selection_seed_commitment",
            "source_optimizer_sha",
            "challenger_sha",
            "challenger_config_digest",
            "calibration_policy_digest",
            "generated_at",
        ):
            object.__setattr__(self, field_name, _non_empty(getattr(self, field_name), field_name))
        if self.holdout_version != HOLDOUT_VALIDATION_MANIFEST_VERSION:
            raise ValueError("unsupported holdout manifest version")
        if self.evidence_role is not EvidenceRole.HOLDOUT_VALIDATION:
            raise ValueError("holdout manifest must use holdout_validation evidence role")
        object.__setattr__(self, "source_snapshot_ref", _ref(self.source_snapshot_ref, "source_snapshot_ref"))
        object.__setattr__(
            self,
            "case_selection_policy_ref",
            _ref(self.case_selection_policy_ref, "case_selection_policy_ref"),
        )
        object.__setattr__(
            self,
            "challenger_policy_ref",
            _ref(self.challenger_policy_ref, "challenger_policy_ref"),
        )
        case_ids = tuple(_non_empty(item, "selected_case_id") for item in self.selected_case_ids)
        scenarios = tuple(_non_empty(item, "scenario_fingerprint") for item in self.scenario_fingerprints)
        if not case_ids or len(set(case_ids)) != len(case_ids):
            raise ValueError("selected_case_ids must be non-empty and unique")
        if len(scenarios) != len(case_ids) or len(set(scenarios)) != len(scenarios):
            raise ValueError("scenario_fingerprints must be unique and align with selected cases")
        object.__setattr__(self, "selected_case_ids", case_ids)
        object.__setattr__(self, "scenario_fingerprints", scenarios)
        roles = tuple(self.required_set_roles)
        if not roles or len(set(roles)) != len(roles):
            raise ValueError("required_set_roles must be non-empty and unique")
        object.__setattr__(self, "required_set_roles", roles)
        revisions = tuple(_non_empty(item, "source_evidence_revision") for item in self.source_evidence_revisions)
        if not revisions:
            raise ValueError("source_evidence_revisions must not be empty")
        object.__setattr__(self, "source_evidence_revisions", revisions)
        if self.human_labels_available_at_freeze:
            raise ValueError("holdout must be frozen before human labels are available")
        if not self.algorithm_identity_hidden:
            raise ValueError("holdout validation requires algorithm identity to remain hidden")
        if self.activation_authorized:
            raise ValueError("holdout manifest cannot authorize optimizer activation")
        if self.personal_dj_model_training_authorized:
            raise ValueError("holdout manifest cannot authorize Personal DJ Model training")


@dataclass(frozen=True, slots=True)
class HoldoutCaseExecutionEvidence:
    case_id: str
    set_role: CuratedSetRole
    outcome: HoldoutSystemOutcome
    scenario_fingerprint: str
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", _non_empty(self.case_id, "case_id"))
        object.__setattr__(
            self,
            "scenario_fingerprint",
            _non_empty(self.scenario_fingerprint, "scenario_fingerprint"),
        )
        refs = tuple(_non_empty(item, "evidence_ref") for item in self.evidence_refs)
        if not refs:
            raise ValueError("holdout case execution evidence must contain evidence refs")
        object.__setattr__(self, "evidence_refs", refs)
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))

    @property
    def human_review_eligible(self) -> bool:
        return self.outcome is HoldoutSystemOutcome.REVIEWABLE_PAIR


@dataclass(frozen=True, slots=True)
class CurationCalibrationPolicyV3:
    policy_id: str = "curation-preference-calibration-v3"
    policy_version: str = CURATION_CALIBRATION_VERSION
    minimum_cases: int = 12
    minimum_reviewed_reviewable_case_fraction: float = 1.0
    minimum_exact_agreement_rate: float = 0.65
    minimum_decisive_agreement_rate: float = 0.70
    minimum_confidence_weighted_decisive_agreement: float = 0.70
    maximum_false_winner_on_human_tie_rate: float = 0.25
    minimum_meaningful_alternative_availability_rate: float = 0.70
    minimum_independent_reviewers_for_multi_dj: int = 3
    maximum_assignment_imbalance: int = 1
    required_set_roles: tuple[CuratedSetRole, ...] = tuple(CuratedSetRole)
    activation_authorized: bool = False
    personal_dj_model_training_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _non_empty(self.policy_id, "policy_id"))
        object.__setattr__(self, "policy_version", _non_empty(self.policy_version, "policy_version"))
        if self.minimum_cases <= 0 or self.minimum_independent_reviewers_for_multi_dj <= 0:
            raise ValueError("minimum case/reviewer counts must be positive")
        if self.maximum_assignment_imbalance < 0:
            raise ValueError("maximum_assignment_imbalance must be non-negative")
        for field_name in (
            "minimum_reviewed_reviewable_case_fraction",
            "minimum_exact_agreement_rate",
            "minimum_decisive_agreement_rate",
            "minimum_confidence_weighted_decisive_agreement",
            "maximum_false_winner_on_human_tie_rate",
            "minimum_meaningful_alternative_availability_rate",
        ):
            object.__setattr__(self, field_name, _unit(getattr(self, field_name), field_name))
        roles = tuple(self.required_set_roles)
        if not roles or len(set(roles)) != len(roles):
            raise ValueError("required_set_roles must be non-empty and unique")
        object.__setattr__(self, "required_set_roles", roles)
        if self.activation_authorized:
            raise ValueError("V3 calibration cannot authorize optimizer activation")
        if self.personal_dj_model_training_authorized:
            raise ValueError("V3 calibration cannot authorize Personal DJ Model training")


@dataclass(frozen=True, slots=True)
class CurationCasePreferenceCalibration:
    case_id: str
    set_role: CuratedSetRole
    review_id: str
    reviewer_ref: str
    assignment_id: str
    human_preference: ResolvedPreference
    challenger_preference: ResolvedPreference
    confidence: float
    exact_agreement: bool | None
    decisive_agreement: bool | None
    reason_codes: tuple[str, ...] = ()
    activation_authorized: bool = False
    personal_dj_model_training_authorized: bool = False

    def __post_init__(self) -> None:
        for field_name in ("case_id", "review_id", "reviewer_ref", "assignment_id"):
            object.__setattr__(self, field_name, _non_empty(getattr(self, field_name), field_name))
        object.__setattr__(self, "confidence", _unit(self.confidence, "confidence"))
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))
        if self.activation_authorized:
            raise ValueError("case calibration cannot authorize optimizer activation")
        if self.personal_dj_model_training_authorized:
            raise ValueError("case calibration cannot authorize Personal DJ Model training")


@dataclass(frozen=True, slots=True)
class CurationCalibrationReportV3:
    report_id: str
    policy_ref: tuple[str, str]
    evidence_role: EvidenceRole
    evaluation_scope: EvaluationScope
    selection_scope: SelectionScope | None
    independent_validation: bool
    representative_performance_claim_allowed: bool
    selected_case_count: int
    reviewable_pair_count: int
    non_reviewable_system_outcome_count: int
    human_reviewed_case_count: int
    reviewer_count: int
    reviewable_pair_fraction: float
    meaningful_alternative_availability_rate: float
    exact_agreement_rate: float | None
    decisive_agreement_rate: float | None
    confidence_weighted_decisive_agreement: float | None
    false_winner_on_human_tie_rate: float | None
    reviewer_disagreement_rate: float | None
    macro_reviewer_agreement_rate: float | None
    pooled_agreement_rate: float | None
    plan_a_greedy_count: int
    plan_b_greedy_count: int
    plan_a_beam_count: int
    plan_b_beam_count: int
    covered_set_roles: tuple[CuratedSetRole, ...]
    missing_set_roles: tuple[CuratedSetRole, ...]
    outcome_counts: tuple[tuple[HoldoutSystemOutcome, int], ...]
    case_evidence: tuple[CurationCasePreferenceCalibration, ...]
    verdict: CalibrationVerdict
    explanation_codes: tuple[str, ...] = ()
    activation_authorized: bool = False
    personal_dj_model_training_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", _non_empty(self.report_id, "report_id"))
        object.__setattr__(self, "policy_ref", _ref(self.policy_ref, "policy_ref"))
        for field_name in (
            "selected_case_count",
            "reviewable_pair_count",
            "non_reviewable_system_outcome_count",
            "human_reviewed_case_count",
            "reviewer_count",
            "plan_a_greedy_count",
            "plan_b_greedy_count",
            "plan_a_beam_count",
            "plan_b_beam_count",
        ):
            value = int(getattr(self, field_name))
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
            object.__setattr__(self, field_name, value)
        if self.reviewable_pair_count + self.non_reviewable_system_outcome_count != self.selected_case_count:
            raise ValueError("system outcome counts must cover the selected-case denominator exactly")
        for field_name in (
            "reviewable_pair_fraction",
            "meaningful_alternative_availability_rate",
            "exact_agreement_rate",
            "decisive_agreement_rate",
            "confidence_weighted_decisive_agreement",
            "false_winner_on_human_tie_rate",
            "reviewer_disagreement_rate",
            "macro_reviewer_agreement_rate",
            "pooled_agreement_rate",
        ):
            object.__setattr__(self, field_name, _unit(getattr(self, field_name), field_name))
        if self.evidence_role is EvidenceRole.DEVELOPMENT_CALIBRATION and self.independent_validation:
            raise ValueError("development calibration cannot claim independent validation")
        if self.selection_scope is SelectionScope.DIAGNOSTIC_CHALLENGE_SET and self.representative_performance_claim_allowed:
            raise ValueError("diagnostic challenge sets cannot make representative performance claims")
        object.__setattr__(self, "covered_set_roles", tuple(self.covered_set_roles))
        object.__setattr__(self, "missing_set_roles", tuple(self.missing_set_roles))
        object.__setattr__(self, "outcome_counts", tuple(self.outcome_counts))
        object.__setattr__(self, "case_evidence", tuple(self.case_evidence))
        object.__setattr__(self, "explanation_codes", tuple(dict.fromkeys(self.explanation_codes)))
        if self.activation_authorized:
            raise ValueError("calibration report cannot authorize optimizer activation")
        if self.personal_dj_model_training_authorized:
            raise ValueError("calibration report cannot authorize Personal DJ Model training")


__all__ = [
    "CURATION_AUDITION_MODE",
    "CURATION_CALIBRATION_VERSION",
    "CURATION_REVIEW_PROTOCOL_VERSION",
    "HOLDOUT_VALIDATION_MANIFEST_VERSION",
    "REQUIRED_CURATION_REVIEW_DIMENSIONS_V2",
    "CurationBlindAssignmentV2",
    "CurationCalibrationPolicyV3",
    "CurationCalibrationReportV3",
    "CurationCasePreferenceCalibration",
    "CurationDJReviewV2",
    "CurationDimensionPairRating",
    "CurationPreference",
    "CurationReviewDimension",
    "EvaluationScope",
    "EvidenceRole",
    "HoldoutCaseExecutionEvidence",
    "HoldoutSystemOutcome",
    "HoldoutValidationManifest",
    "SelectionScope",
]
