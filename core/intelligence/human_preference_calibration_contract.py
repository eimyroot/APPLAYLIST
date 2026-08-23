from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from core.intelligence.curated_real_library_review_contract import CuratedSetRole

HUMAN_PREFERENCE_CALIBRATION_VERSION = "human-preference-calibration-r2"


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


class ResolvedPreference(StrEnum):
    GREEDY = "greedy"
    BEAM = "beam"
    TIE = "tie"
    ABSTAIN = "abstain"
    NOT_PROVEN = "not_proven"


class CalibrationVerdict(StrEnum):
    INCOMPLETE = "incomplete"
    DOES_NOT_SUPPORT_ACTIVATION = "does_not_support_activation"
    SUPPORTS_FURTHER_EVALUATION = "supports_further_evaluation"


@dataclass(frozen=True, slots=True)
class HumanPreferenceCalibrationPolicy:
    policy_id: str = "human-preference-calibration-r2"
    policy_version: str = HUMAN_PREFERENCE_CALIBRATION_VERSION
    minimum_cases: int = 12
    minimum_reviewed_case_fraction: float = 1.0
    minimum_decisive_judgments: int = 6
    minimum_exact_agreement_rate: float = 0.65
    minimum_decisive_agreement_rate: float = 0.70
    minimum_confidence_weighted_decisive_agreement: float = 0.70
    maximum_false_winner_on_human_tie_rate: float = 0.25
    required_set_roles: tuple[CuratedSetRole, ...] = tuple(CuratedSetRole)
    activation_authorized: bool = False
    personal_dj_model_training_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _non_empty(self.policy_id, "policy_id"))
        object.__setattr__(
            self,
            "policy_version",
            _non_empty(self.policy_version, "policy_version"),
        )
        if self.minimum_cases <= 0 or self.minimum_decisive_judgments <= 0:
            raise ValueError("minimum case and decisive judgment counts must be positive")
        for field_name in (
            "minimum_reviewed_case_fraction",
            "minimum_exact_agreement_rate",
            "minimum_decisive_agreement_rate",
            "minimum_confidence_weighted_decisive_agreement",
            "maximum_false_winner_on_human_tie_rate",
        ):
            object.__setattr__(self, field_name, _unit(getattr(self, field_name), field_name))
        roles = tuple(self.required_set_roles)
        if not roles or len(set(roles)) != len(roles):
            raise ValueError("required_set_roles must be non-empty and unique")
        object.__setattr__(self, "required_set_roles", roles)
        if self.activation_authorized:
            raise ValueError("R2 calibration cannot authorize optimizer activation")
        if self.personal_dj_model_training_authorized:
            raise ValueError("R2 calibration cannot authorize Personal DJ Model training")


@dataclass(frozen=True, slots=True)
class CasePreferenceCalibration:
    case_id: str
    set_role: CuratedSetRole
    review_id: str
    reviewer_ref: str
    assignment_id: str
    human_preference: ResolvedPreference
    challenger_preference: ResolvedPreference
    human_confidence: float
    exact_agreement: bool | None
    decisive_agreement: bool | None
    human_algorithm_identity_hidden: bool
    source_identity_preserved: bool = True
    reason_codes: tuple[str, ...] = ()
    activation_authorized: bool = False
    personal_dj_model_training_authorized: bool = False

    def __post_init__(self) -> None:
        for field_name in ("case_id", "review_id", "reviewer_ref", "assignment_id"):
            object.__setattr__(self, field_name, _non_empty(getattr(self, field_name), field_name))
        object.__setattr__(self, "human_confidence", _unit(self.human_confidence, "human_confidence"))
        if not self.human_algorithm_identity_hidden:
            raise ValueError("calibration requires genuinely blinded human review evidence")
        if not self.source_identity_preserved:
            raise ValueError("calibration must preserve source path identity")
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))
        if self.activation_authorized:
            raise ValueError("case calibration cannot authorize optimizer activation")
        if self.personal_dj_model_training_authorized:
            raise ValueError("case calibration cannot authorize Personal DJ Model training")


@dataclass(frozen=True, slots=True)
class PreferenceConfusionCell:
    human_preference: ResolvedPreference
    challenger_preference: ResolvedPreference
    count: int

    def __post_init__(self) -> None:
        if self.count < 0:
            raise ValueError("confusion count must be non-negative")


@dataclass(frozen=True, slots=True)
class HumanPreferenceCalibrationReport:
    report_id: str
    policy_ref: tuple[str, str]
    case_count: int
    reviewed_case_count: int
    abstain_count: int
    decisive_human_count: int
    exact_agreement_count: int
    decisive_agreement_count: int
    human_tie_count: int
    challenger_tie_count: int
    false_winner_on_human_tie_count: int
    challenger_tie_on_human_decisive_count: int
    reviewed_case_fraction: float
    exact_agreement_rate: float | None
    decisive_agreement_rate: float | None
    confidence_weighted_decisive_agreement: float | None
    false_winner_on_human_tie_rate: float | None
    covered_set_roles: tuple[CuratedSetRole, ...]
    missing_set_roles: tuple[CuratedSetRole, ...]
    confusion_matrix: tuple[PreferenceConfusionCell, ...]
    case_evidence: tuple[CasePreferenceCalibration, ...]
    verdict: CalibrationVerdict
    explanation_codes: tuple[str, ...] = ()
    activation_authorized: bool = False
    personal_dj_model_training_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", _non_empty(self.report_id, "report_id"))
        if len(self.policy_ref) != 2:
            raise ValueError("policy_ref must contain exactly two values")
        object.__setattr__(
            self,
            "policy_ref",
            (
                _non_empty(self.policy_ref[0], "policy_ref[0]"),
                _non_empty(self.policy_ref[1], "policy_ref[1]"),
            ),
        )
        for field_name in (
            "case_count",
            "reviewed_case_count",
            "abstain_count",
            "decisive_human_count",
            "exact_agreement_count",
            "decisive_agreement_count",
            "human_tie_count",
            "challenger_tie_count",
            "false_winner_on_human_tie_count",
            "challenger_tie_on_human_decisive_count",
        ):
            value = int(getattr(self, field_name))
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
            object.__setattr__(self, field_name, value)
        if self.reviewed_case_count > self.case_count:
            raise ValueError("reviewed_case_count cannot exceed case_count")
        for field_name in (
            "reviewed_case_fraction",
            "exact_agreement_rate",
            "decisive_agreement_rate",
            "confidence_weighted_decisive_agreement",
            "false_winner_on_human_tie_rate",
        ):
            object.__setattr__(self, field_name, _unit(getattr(self, field_name), field_name))
        object.__setattr__(self, "covered_set_roles", tuple(self.covered_set_roles))
        object.__setattr__(self, "missing_set_roles", tuple(self.missing_set_roles))
        object.__setattr__(self, "confusion_matrix", tuple(self.confusion_matrix))
        object.__setattr__(self, "case_evidence", tuple(self.case_evidence))
        object.__setattr__(self, "explanation_codes", tuple(dict.fromkeys(self.explanation_codes)))
        if self.activation_authorized:
            raise ValueError("calibration report cannot authorize optimizer activation")
        if self.personal_dj_model_training_authorized:
            raise ValueError("calibration report cannot authorize Personal DJ Model training")


__all__ = [
    "HUMAN_PREFERENCE_CALIBRATION_VERSION",
    "CalibrationVerdict",
    "CasePreferenceCalibration",
    "HumanPreferenceCalibrationPolicy",
    "HumanPreferenceCalibrationReport",
    "PreferenceConfusionCell",
    "ResolvedPreference",
]
