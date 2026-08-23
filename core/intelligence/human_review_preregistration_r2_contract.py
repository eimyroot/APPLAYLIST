from __future__ import annotations

from dataclasses import dataclass

from core.intelligence.human_review_protocol_r2_contract import (
    CurationJudgmentMode,
    PriorCaseExposure,
)

HUMAN_REVIEW_PREREGISTRATION_R2_VERSION = "human-review-preregistration-r2"
HOLDOUT_REPLACEMENT_POLICY_R2_VERSION = "holdout-replacement-policy-r2"
HOLDOUT_EFFECTIVE_COHORT_R2_VERSION = "holdout-effective-cohort-r2"
CURATION_CALIBRATION_BINDING_R3_VERSION = "curation-calibration-binding-r3"


def _text(value: str, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    return normalized


@dataclass(frozen=True, slots=True)
class CurationCleanAttestationR2:
    attestation_id: str
    review_id: str
    curation_session_id: str
    observed_at: str
    prior_case_exposure: PriorCaseExposure
    judgment_mode: CurationJudgmentMode
    transition_execution_used: bool
    transition_preview_heard: bool
    algorithm_identity_was_hidden: bool
    attestation_version: str = HUMAN_REVIEW_PREREGISTRATION_R2_VERSION
    reason_codes: tuple[str, ...] = ()
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        for field in (
            "attestation_id",
            "review_id",
            "curation_session_id",
            "observed_at",
            "attestation_version",
        ):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        if type(self.transition_execution_used) is not bool:
            raise ValueError("transition_execution_used must be explicit boolean")
        if type(self.transition_preview_heard) is not bool:
            raise ValueError("transition_preview_heard must be explicit boolean")
        if type(self.algorithm_identity_was_hidden) is not bool:
            raise ValueError("algorithm_identity_was_hidden must be explicit boolean")
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))
        if self.activation_authorized:
            raise ValueError("CurationCleanAttestationR2 cannot authorize activation")

    @property
    def clean_sequence_only(self) -> bool:
        return bool(
            self.prior_case_exposure is PriorCaseExposure.NO
            and self.judgment_mode is CurationJudgmentMode.SEQUENCE_ONLY
            and not self.transition_execution_used
            and not self.transition_preview_heard
            and self.algorithm_identity_was_hidden
        )


@dataclass(frozen=True, slots=True)
class HoldoutReplacementPolicyR2:
    policy_id: str
    selection_manifest_fingerprint: str
    preregistration_manifest_fingerprint: str
    frozen_at: str
    allowed_technical_invalidity_reasons: tuple[str, ...]
    policy_version: str = HOLDOUT_REPLACEMENT_POLICY_R2_VERSION
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        for field in (
            "policy_id",
            "selection_manifest_fingerprint",
            "preregistration_manifest_fingerprint",
            "frozen_at",
            "policy_version",
        ):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        reasons = tuple(
            _text(item, "allowed_technical_invalidity_reason")
            for item in self.allowed_technical_invalidity_reasons
        )
        if not reasons or len(set(reasons)) != len(reasons):
            raise ValueError("allowed technical invalidity reasons must be non-empty and unique")
        forbidden_tokens = (
            "preference",
            "rating",
            "score",
            "challenger",
            "human",
            "like",
            "dislike",
        )
        for reason in reasons:
            if any(token in reason.lower() for token in forbidden_tokens):
                raise ValueError("replacement policy reason is preference/challenger contaminated")
        object.__setattr__(self, "allowed_technical_invalidity_reasons", reasons)
        if self.activation_authorized:
            raise ValueError("HoldoutReplacementPolicyR2 cannot authorize activation")


@dataclass(frozen=True, slots=True)
class HoldoutReplacementEventR2:
    event_id: str
    invalid_case_id: str
    replacement_case_id: str
    technical_invalidity_reason: str
    fallback_ordinal: int
    event_version: str = HOLDOUT_EFFECTIVE_COHORT_R2_VERSION
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        for field in (
            "event_id",
            "invalid_case_id",
            "replacement_case_id",
            "technical_invalidity_reason",
            "event_version",
        ):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        if self.invalid_case_id == self.replacement_case_id:
            raise ValueError("replacement event requires distinct invalid/replacement case ids")
        if self.fallback_ordinal < 0:
            raise ValueError("fallback_ordinal must be non-negative")
        if self.activation_authorized:
            raise ValueError("HoldoutReplacementEventR2 cannot authorize activation")


@dataclass(frozen=True, slots=True)
class EffectiveHoldoutCohortR2:
    cohort_id: str
    selection_manifest_fingerprint: str
    replacement_policy_fingerprint: str
    preregistration_manifest_fingerprint: str
    effective_case_ids: tuple[str, ...]
    replacement_events: tuple[HoldoutReplacementEventR2, ...]
    cohort_version: str = HOLDOUT_EFFECTIVE_COHORT_R2_VERSION
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        for field in (
            "cohort_id",
            "selection_manifest_fingerprint",
            "replacement_policy_fingerprint",
            "preregistration_manifest_fingerprint",
            "cohort_version",
        ):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        cases = tuple(_text(item, "effective_case_id") for item in self.effective_case_ids)
        if not cases or len(set(cases)) != len(cases):
            raise ValueError("effective_case_ids must be non-empty and unique")
        object.__setattr__(self, "effective_case_ids", cases)
        events = tuple(self.replacement_events)
        invalid_ids = tuple(item.invalid_case_id for item in events)
        replacement_ids = tuple(item.replacement_case_id for item in events)
        if len(set(invalid_ids)) != len(invalid_ids):
            raise ValueError("invalid holdout case may be replaced at most once")
        if len(set(replacement_ids)) != len(replacement_ids):
            raise ValueError("fallback holdout case may be used at most once")
        object.__setattr__(self, "replacement_events", events)
        if self.activation_authorized:
            raise ValueError("EffectiveHoldoutCohortR2 cannot authorize activation")


@dataclass(frozen=True, slots=True)
class CurationCalibrationBindingR3:
    binding_id: str
    case_id: str
    review_id: str
    curation_session_id: str
    attestation_fingerprint: str
    selection_manifest_fingerprint: str
    binding_version: str = CURATION_CALIBRATION_BINDING_R3_VERSION
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        for field in (
            "binding_id",
            "case_id",
            "review_id",
            "curation_session_id",
            "attestation_fingerprint",
            "selection_manifest_fingerprint",
            "binding_version",
        ):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        if self.activation_authorized:
            raise ValueError("CurationCalibrationBindingR3 cannot authorize activation")


__all__ = [
    "CURATION_CALIBRATION_BINDING_R3_VERSION",
    "CurationCalibrationBindingR3",
    "CurationCleanAttestationR2",
    "EffectiveHoldoutCohortR2",
    "HOLDOUT_EFFECTIVE_COHORT_R2_VERSION",
    "HOLDOUT_REPLACEMENT_POLICY_R2_VERSION",
    "HUMAN_REVIEW_PREREGISTRATION_R2_VERSION",
    "HoldoutReplacementEventR2",
    "HoldoutReplacementPolicyR2",
]
