from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from core.intelligence.curated_real_library_review_contract import (
    CuratedReviewCase,
    CuratedSetRole,
)

HUMAN_REVIEW_PROTOCOL_R2_VERSION = "human-dj-review-r2"
CURATION_CALIBRATION_R3_VERSION = "curation-calibration-r3"
HOLDOUT_SAMPLING_POLICY_VERSION = "holdout-case-sampling-r1"


def _text(value: str, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    return normalized


def _unit(value: float, field: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field} must be between 0 and 1")
    return numeric


def _score(value: float, field: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric) or not 1.0 <= numeric <= 5.0:
        raise ValueError(f"{field} must be between 1 and 5")
    return numeric


def _positive(value: float, field: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric) or numeric <= 0.0:
        raise ValueError(f"{field} must be finite and positive")
    return numeric


def _window(value: tuple[float, float], field: str) -> tuple[float, float]:
    if len(value) != 2:
        raise ValueError(f"{field} must contain exactly two coordinates")
    start = float(value[0])
    end = float(value[1])
    if not math.isfinite(start) or not math.isfinite(end) or start < 0.0 or end <= start:
        raise ValueError(f"{field} must be a finite increasing non-negative window")
    return (start, end)


class ReviewDatasetRole(StrEnum):
    DEVELOPMENT_REGRESSION = "development_regression"
    PERSONAL_HOLDOUT = "personal_holdout"
    GENERAL_HOLDOUT = "general_holdout"


class ValidationClaimScope(StrEnum):
    PERSONAL_DJ_CALIBRATION = "personal_dj_calibration"
    GENERAL_DJ_PRODUCT_VALIDATION = "general_dj_product_validation"


class CurationJudgmentMode(StrEnum):
    SEQUENCE_ONLY = "sequence_only"


class PriorCaseExposure(StrEnum):
    NO = "no"
    YES = "yes"
    UNSURE = "unsure"


class CurationDimension(StrEnum):
    ENERGY_FLOW = "energy_flow"
    DRAMATURGICAL_FIT = "dramaturgical_fit"
    SET_COHERENCE = "set_coherence"
    ALTERNATIVE_USEFULNESS = "alternative_usefulness"


REQUIRED_CURATION_DIMENSIONS_R2 = tuple(CurationDimension)


class CurationPreference(StrEnum):
    PLAN_A = "plan_a"
    PLAN_B = "plan_b"
    TIE = "tie"
    ABSTAIN = "abstain"


class ResolvedCurationPreference(StrEnum):
    GREEDY = "greedy"
    BEAM = "beam"
    TIE = "tie"
    ABSTAIN = "abstain"
    NOT_PROVEN = "not_proven"


class MeaningfulDifferenceStatus(StrEnum):
    MEANINGFULLY_DISTINCT = "meaningfully_distinct"
    NEAR_EQUIVALENT = "near_equivalent"
    NOT_PROVEN_MISSING_EVIDENCE = "not_proven_missing_evidence"


class Assessability(StrEnum):
    ASSESSABLE = "assessable"
    NOT_ASSESSABLE = "not_assessable"


class TransitionFeasibilityDimension(StrEnum):
    PHRASE_WINDOW_FEASIBILITY = "phrase_window_feasibility"
    ENERGY_HANDOFF_FEASIBILITY = "energy_handoff_feasibility"
    SPECTRAL_COMPATIBILITY_EVIDENCE = "spectral_compatibility_evidence"
    TEMPO_FEASIBILITY = "tempo_feasibility"
    HARMONIC_COMPATIBILITY = "harmonic_compatibility"
    TRANSITION_STRATEGY_SUITABILITY = "transition_strategy_suitability"
    VOCAL_COLLISION_RISK = "vocal_collision_risk"


class CurationCalibrationVerdict(StrEnum):
    INCOMPLETE = "incomplete"
    DOES_NOT_SUPPORT_FURTHER_EVALUATION = "does_not_support_further_evaluation"
    SUPPORTS_FURTHER_EVALUATION = "supports_further_evaluation"


@dataclass(frozen=True, slots=True)
class CurationDimensionPairRating:
    dimension: CurationDimension
    plan_a_score: float
    plan_b_score: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_a_score", _score(self.plan_a_score, "plan_a_score"))
        object.__setattr__(self, "plan_b_score", _score(self.plan_b_score, "plan_b_score"))


@dataclass(frozen=True, slots=True)
class CurationReviewR2:
    review_id: str
    assignment_id: str
    reviewer_ref: str
    curation_session_id: str
    dataset_role: ReviewDatasetRole
    preference: CurationPreference
    ratings: tuple[CurationDimensionPairRating, ...]
    confidence: float
    observed_at: str
    prior_case_exposure: PriorCaseExposure = PriorCaseExposure.NO
    judgment_mode: CurationJudgmentMode = CurationJudgmentMode.SEQUENCE_ONLY
    transition_execution_used: bool = False
    transition_preview_heard: bool = False
    algorithm_identity_was_hidden: bool = True
    reason_codes: tuple[str, ...] = ()
    notes: str | None = None
    activation_authorized: bool = False
    personal_dj_model_training_authorized: bool = False

    def __post_init__(self) -> None:
        for field in ("review_id", "assignment_id", "reviewer_ref", "curation_session_id", "observed_at"):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        ratings = tuple(self.ratings)
        dimensions = tuple(item.dimension for item in ratings)
        if len(dimensions) != len(REQUIRED_CURATION_DIMENSIONS_R2) or set(dimensions) != set(
            REQUIRED_CURATION_DIMENSIONS_R2
        ):
            raise ValueError("CurationReviewR2 requires exactly the four R2 curation dimensions")
        object.__setattr__(self, "ratings", ratings)
        object.__setattr__(self, "confidence", _unit(self.confidence, "confidence"))
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))
        if self.notes is not None:
            object.__setattr__(self, "notes", str(self.notes))
        if not self.algorithm_identity_was_hidden:
            raise ValueError("blinded curation review requires algorithm identity to remain hidden")
        if self.activation_authorized or self.personal_dj_model_training_authorized:
            raise ValueError("CurationReviewR2 cannot authorize activation or PDM training")

    @property
    def clean_holdout_eligible(self) -> bool:
        return bool(
            self.dataset_role in (ReviewDatasetRole.PERSONAL_HOLDOUT, ReviewDatasetRole.GENERAL_HOLDOUT)
            and self.prior_case_exposure is PriorCaseExposure.NO
            and self.judgment_mode is CurationJudgmentMode.SEQUENCE_ONLY
            and not self.transition_execution_used
            and not self.transition_preview_heard
            and self.algorithm_identity_was_hidden
        )


@dataclass(frozen=True, slots=True)
class HoldoutCandidate:
    candidate_id: str
    case_id: str
    set_role: CuratedSetRole
    engineering_acceptance_passed: bool
    technical_invalidity_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", _text(self.candidate_id, "candidate_id"))
        object.__setattr__(self, "case_id", _text(self.case_id, "case_id"))
        if self.technical_invalidity_reason is not None:
            object.__setattr__(
                self,
                "technical_invalidity_reason",
                _text(self.technical_invalidity_reason, "technical_invalidity_reason"),
            )

    @property
    def technically_eligible(self) -> bool:
        return self.engineering_acceptance_passed and self.technical_invalidity_reason is None


@dataclass(frozen=True, slots=True)
class HoldoutCaseSamplingPolicy:
    policy_id: str
    dataset_role: ReviewDatasetRole
    canonical_sha: str
    snapshot_fingerprint: str
    eligible_scope_fingerprint: str
    source_case_generator_version: str
    sampling_seed: str
    role_quotas: tuple[tuple[CuratedSetRole, int], ...]
    fallback_count: int = 12
    policy_version: str = HOLDOUT_SAMPLING_POLICY_VERSION
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        for field in (
            "policy_id",
            "canonical_sha",
            "snapshot_fingerprint",
            "eligible_scope_fingerprint",
            "source_case_generator_version",
            "sampling_seed",
            "policy_version",
        ):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        if self.dataset_role is ReviewDatasetRole.DEVELOPMENT_REGRESSION:
            raise ValueError("holdout sampling policy cannot target development/regression data")
        quotas = tuple(self.role_quotas)
        roles = tuple(role for role, _ in quotas)
        if not quotas or len(set(roles)) != len(roles):
            raise ValueError("role_quotas must be non-empty and unique")
        for _, count in quotas:
            if int(count) <= 0:
                raise ValueError("each holdout role quota must be positive")
        object.__setattr__(self, "role_quotas", tuple((role, int(count)) for role, count in quotas))
        if self.fallback_count < 0:
            raise ValueError("fallback_count must be non-negative")
        if self.activation_authorized:
            raise ValueError("holdout sampling cannot authorize activation")


@dataclass(frozen=True, slots=True)
class HoldoutSelectionEntry:
    candidate_id: str
    case_id: str
    set_role: CuratedSetRole
    sampling_ordinal: int
    selected: bool
    reason_code: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", _text(self.candidate_id, "candidate_id"))
        object.__setattr__(self, "case_id", _text(self.case_id, "case_id"))
        if self.sampling_ordinal < 0:
            raise ValueError("sampling_ordinal must be non-negative")
        object.__setattr__(self, "reason_code", _text(self.reason_code, "reason_code"))


@dataclass(frozen=True, slots=True)
class HoldoutSelectionResult:
    policy_ref: tuple[str, str]
    selected_case_ids: tuple[str, ...]
    fallback_case_ids: tuple[str, ...]
    ledger: tuple[HoldoutSelectionEntry, ...]
    manifest_fingerprint: str
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        if len(self.policy_ref) != 2:
            raise ValueError("policy_ref must contain policy id/version")
        object.__setattr__(self, "policy_ref", tuple(_text(item, "policy_ref") for item in self.policy_ref))
        if len(set(self.selected_case_ids)) != len(self.selected_case_ids):
            raise ValueError("selected_case_ids must be unique")
        if set(self.selected_case_ids) & set(self.fallback_case_ids):
            raise ValueError("selected and fallback case ids must be disjoint")
        object.__setattr__(self, "manifest_fingerprint", _text(self.manifest_fingerprint, "manifest_fingerprint"))
        if self.activation_authorized:
            raise ValueError("holdout selection cannot authorize activation")


@dataclass(frozen=True, slots=True)
class TransitionReviewSpecR2:
    spec_id: str
    outgoing_track_id: str
    incoming_track_id: str
    outgoing_segment_id: str
    incoming_segment_id: str
    outgoing_analysis_revision: str
    incoming_analysis_revision: str
    outgoing_evidence_fingerprint: str
    incoming_evidence_fingerprint: str
    outgoing_window_seconds: tuple[float, float]
    incoming_window_seconds: tuple[float, float]
    duration_seconds: float
    strategy_id: str
    strategy_version: str
    evidence_refs: tuple[str, ...]
    target_bpm: float | None = None
    tempo_unchanged: bool = False
    duration_bars: float | None = None
    beat_grid_revision: str | None = None
    technique_policy: tuple[tuple[str, str], ...] = ()
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        for field in (
            "spec_id",
            "outgoing_track_id",
            "incoming_track_id",
            "outgoing_segment_id",
            "incoming_segment_id",
            "outgoing_analysis_revision",
            "incoming_analysis_revision",
            "outgoing_evidence_fingerprint",
            "incoming_evidence_fingerprint",
            "strategy_id",
            "strategy_version",
        ):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        if self.outgoing_track_id == self.incoming_track_id:
            raise ValueError("transition spec requires distinct outgoing/incoming tracks")
        object.__setattr__(self, "outgoing_window_seconds", _window(self.outgoing_window_seconds, "outgoing_window_seconds"))
        object.__setattr__(self, "incoming_window_seconds", _window(self.incoming_window_seconds, "incoming_window_seconds"))
        object.__setattr__(self, "duration_seconds", _positive(self.duration_seconds, "duration_seconds"))
        if self.duration_bars is not None:
            object.__setattr__(self, "duration_bars", _positive(self.duration_bars, "duration_bars"))
        if self.tempo_unchanged:
            if self.target_bpm is not None:
                raise ValueError("target_bpm must be absent when tempo_unchanged=true")
        else:
            if self.target_bpm is None:
                raise ValueError("target_bpm is required unless tempo_unchanged=true")
            object.__setattr__(self, "target_bpm", _positive(self.target_bpm, "target_bpm"))
        if self.beat_grid_revision is not None:
            object.__setattr__(self, "beat_grid_revision", _text(self.beat_grid_revision, "beat_grid_revision"))
        policy = tuple((_text(key, "technique_policy key"), _text(value, "technique_policy value")) for key, value in self.technique_policy)
        if len({key for key, _ in policy}) != len(policy):
            raise ValueError("technique_policy keys must be unique")
        object.__setattr__(self, "technique_policy", policy)
        refs = tuple(_text(item, "evidence_ref") for item in self.evidence_refs)
        if not refs:
            raise ValueError("transition spec requires evidence refs")
        object.__setattr__(self, "evidence_refs", refs)
        if self.activation_authorized:
            raise ValueError("TransitionReviewSpecR2 cannot authorize activation")


@dataclass(frozen=True, slots=True)
class TransitionDimensionEvidenceR2:
    dimension: TransitionFeasibilityDimension
    assessability: Assessability
    value: float | None
    reason_code: str | None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.assessability is Assessability.ASSESSABLE:
            if self.value is None:
                raise ValueError("assessable transition dimension requires a value")
            object.__setattr__(self, "value", _unit(self.value, "value"))
            if self.reason_code is not None:
                raise ValueError("assessable transition dimension cannot carry not-assessable reason")
            refs = tuple(_text(item, "evidence_ref") for item in self.evidence_refs)
            if not refs:
                raise ValueError("assessable transition dimension requires evidence refs")
            object.__setattr__(self, "evidence_refs", refs)
        else:
            if self.value is not None:
                raise ValueError("not_assessable transition dimension cannot carry a value")
            object.__setattr__(self, "reason_code", _text(self.reason_code or "", "reason_code"))
            object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class TransitionFeasibilityEvidenceR2:
    evidence_id: str
    transition_spec_fingerprint: str
    dimensions: tuple[TransitionDimensionEvidenceR2, ...]
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _text(self.evidence_id, "evidence_id"))
        object.__setattr__(
            self,
            "transition_spec_fingerprint",
            _text(self.transition_spec_fingerprint, "transition_spec_fingerprint"),
        )
        dimensions = tuple(self.dimensions)
        keys = tuple(item.dimension for item in dimensions)
        if len(set(keys)) != len(keys):
            raise ValueError("transition feasibility dimensions must be unique")
        object.__setattr__(self, "dimensions", dimensions)
        if self.activation_authorized:
            raise ValueError("TransitionFeasibilityEvidenceR2 cannot authorize activation")


@dataclass(frozen=True, slots=True)
class HumanTransitionAuditionReviewR2:
    review_id: str
    transition_spec_fingerprint: str
    reviewer_ref: str
    observed_at: str
    rendered_preview_fingerprint: str | None = None
    standardized_execution_recipe_fingerprint: str | None = None
    reason_codes: tuple[str, ...] = ()
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        for field in ("review_id", "transition_spec_fingerprint", "reviewer_ref", "observed_at"):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        if not self.rendered_preview_fingerprint and not self.standardized_execution_recipe_fingerprint:
            raise ValueError("human transition audition requires rendered preview or standardized recipe")
        if self.rendered_preview_fingerprint is not None:
            object.__setattr__(
                self,
                "rendered_preview_fingerprint",
                _text(self.rendered_preview_fingerprint, "rendered_preview_fingerprint"),
            )
        if self.standardized_execution_recipe_fingerprint is not None:
            object.__setattr__(
                self,
                "standardized_execution_recipe_fingerprint",
                _text(self.standardized_execution_recipe_fingerprint, "standardized_execution_recipe_fingerprint"),
            )
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))
        if self.activation_authorized:
            raise ValueError("HumanTransitionAuditionReviewR2 cannot authorize activation")


@dataclass(frozen=True, slots=True)
class HumanExecutionReviewR2:
    review_id: str
    reviewer_ref: str
    execution_session_id: str
    observed_at: str
    free_form_execution: bool
    standardized_execution_recipe_fingerprint: str | None = None
    reason_codes: tuple[str, ...] = ()
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        for field in ("review_id", "reviewer_ref", "execution_session_id", "observed_at"):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        if self.standardized_execution_recipe_fingerprint is not None:
            object.__setattr__(
                self,
                "standardized_execution_recipe_fingerprint",
                _text(self.standardized_execution_recipe_fingerprint, "standardized_execution_recipe_fingerprint"),
            )
        if not self.free_form_execution and self.standardized_execution_recipe_fingerprint is None:
            raise ValueError("non-free-form execution review requires standardized recipe fingerprint")
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))
        if self.activation_authorized:
            raise ValueError("HumanExecutionReviewR2 cannot authorize activation")


@dataclass(frozen=True, slots=True)
class CurationCalibrationCaseR3:
    case: CuratedReviewCase
    dataset_role: ReviewDatasetRole
    meaningful_difference_status: MeaningfulDifferenceStatus
    selection_manifest_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "selection_manifest_fingerprint",
            _text(self.selection_manifest_fingerprint, "selection_manifest_fingerprint"),
        )


@dataclass(frozen=True, slots=True)
class CurationCalibrationEvidenceR3:
    case_id: str
    set_role: CuratedSetRole
    review_id: str
    reviewer_ref: str
    assignment_id: str
    dataset_role: ReviewDatasetRole
    meaningful_difference_status: MeaningfulDifferenceStatus
    human_preference: ResolvedCurationPreference
    challenger_preference: ResolvedCurationPreference
    human_confidence: float
    exact_agreement: bool | None
    decisive_agreement: bool | None
    clean_holdout_eligible: bool
    reason_codes: tuple[str, ...]
    activation_authorized: bool = False
    personal_dj_model_training_authorized: bool = False

    def __post_init__(self) -> None:
        for field in ("case_id", "review_id", "reviewer_ref", "assignment_id"):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        object.__setattr__(self, "human_confidence", _unit(self.human_confidence, "human_confidence"))
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))
        if self.activation_authorized or self.personal_dj_model_training_authorized:
            raise ValueError("CurationCalibrationEvidenceR3 cannot authorize activation or PDM training")


@dataclass(frozen=True, slots=True)
class WilsonInterval:
    lower: float
    upper: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "lower", _unit(self.lower, "lower"))
        object.__setattr__(self, "upper", _unit(self.upper, "upper"))
        if self.lower > self.upper:
            raise ValueError("Wilson interval lower must not exceed upper")


@dataclass(frozen=True, slots=True)
class CurationCalibrationPolicyR3:
    policy_id: str = "personal-curation-calibration-r3"
    policy_version: str = CURATION_CALIBRATION_R3_VERSION
    claim_scope: ValidationClaimScope = ValidationClaimScope.PERSONAL_DJ_CALIBRATION
    minimum_clean_cases: int = 24
    minimum_decisive_cases: int = 12
    minimum_exact_agreement_lower_bound: float = 0.50
    minimum_decisive_agreement_lower_bound: float = 0.50
    maximum_false_winner_on_human_tie_rate: float = 0.25
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _text(self.policy_id, "policy_id"))
        object.__setattr__(self, "policy_version", _text(self.policy_version, "policy_version"))
        if self.minimum_clean_cases <= 0 or self.minimum_decisive_cases <= 0:
            raise ValueError("minimum calibration case counts must be positive")
        for field in (
            "minimum_exact_agreement_lower_bound",
            "minimum_decisive_agreement_lower_bound",
            "maximum_false_winner_on_human_tie_rate",
        ):
            object.__setattr__(self, field, _unit(getattr(self, field), field))
        if self.activation_authorized:
            raise ValueError("CurationCalibrationPolicyR3 cannot authorize activation")


@dataclass(frozen=True, slots=True)
class CurationCalibrationReportR3:
    report_id: str
    policy_ref: tuple[str, str]
    claim_scope: ValidationClaimScope
    clean_case_count: int
    excluded_case_count: int
    decisive_case_count: int
    exact_agreement_count: int
    decisive_agreement_count: int
    human_tie_count: int
    false_winner_on_human_tie_count: int
    exact_agreement_rate: float | None
    decisive_agreement_rate: float | None
    false_winner_on_human_tie_rate: float | None
    exact_agreement_interval: WilsonInterval | None
    decisive_agreement_interval: WilsonInterval | None
    covered_set_roles: tuple[CuratedSetRole, ...]
    missing_set_roles: tuple[CuratedSetRole, ...]
    case_evidence: tuple[CurationCalibrationEvidenceR3, ...]
    verdict: CurationCalibrationVerdict
    explanation_codes: tuple[str, ...]
    activation_authorized: bool = False
    personal_dj_model_training_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", _text(self.report_id, "report_id"))
        if len(self.policy_ref) != 2:
            raise ValueError("policy_ref must contain policy id/version")
        object.__setattr__(self, "policy_ref", tuple(_text(item, "policy_ref") for item in self.policy_ref))
        for field in (
            "clean_case_count",
            "excluded_case_count",
            "decisive_case_count",
            "exact_agreement_count",
            "decisive_agreement_count",
            "human_tie_count",
            "false_winner_on_human_tie_count",
        ):
            if getattr(self, field) < 0:
                raise ValueError(f"{field} must be non-negative")
        for field in ("exact_agreement_rate", "decisive_agreement_rate", "false_winner_on_human_tie_rate"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, _unit(value, field))
        object.__setattr__(self, "case_evidence", tuple(self.case_evidence))
        object.__setattr__(self, "explanation_codes", tuple(dict.fromkeys(self.explanation_codes)))
        if self.activation_authorized or self.personal_dj_model_training_authorized:
            raise ValueError("CurationCalibrationReportR3 cannot authorize activation or PDM training")


__all__ = [
    "Assessability",
    "CurationCalibrationCaseR3",
    "CurationCalibrationEvidenceR3",
    "CurationCalibrationPolicyR3",
    "CurationCalibrationReportR3",
    "CurationCalibrationVerdict",
    "CurationDimension",
    "CurationDimensionPairRating",
    "CurationJudgmentMode",
    "CurationPreference",
    "CurationReviewR2",
    "HOLDOUT_SAMPLING_POLICY_VERSION",
    "HUMAN_REVIEW_PROTOCOL_R2_VERSION",
    "CURATION_CALIBRATION_R3_VERSION",
    "HoldoutCandidate",
    "HoldoutCaseSamplingPolicy",
    "HoldoutSelectionEntry",
    "HoldoutSelectionResult",
    "HumanExecutionReviewR2",
    "HumanTransitionAuditionReviewR2",
    "MeaningfulDifferenceStatus",
    "PriorCaseExposure",
    "REQUIRED_CURATION_DIMENSIONS_R2",
    "ResolvedCurationPreference",
    "ReviewDatasetRole",
    "TransitionDimensionEvidenceR2",
    "TransitionFeasibilityDimension",
    "TransitionFeasibilityEvidenceR2",
    "TransitionReviewSpecR2",
    "ValidationClaimScope",
    "WilsonInterval",
]
