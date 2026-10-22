from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.intelligence.curation_review_v2_contract import SelectionScope

HOLDOUT_GUARD_VERSION = "curation-holdout-guard-r1"


def _non_empty(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


class HoldoutSelectionInput(StrEnum):
    SOURCE_LIBRARY_ELIGIBILITY = "source_library_eligibility"
    SET_ROLE = "set_role"
    DETERMINISTIC_SEED = "deterministic_seed"
    BPM_STRATUM = "bpm_stratum"
    STYLE_STRATUM = "style_stratum"
    ENERGY_STRATUM = "energy_stratum"
    CHALLENGER_SCORE = "challenger_score"
    CHALLENGER_PREFERENCE = "challenger_preference"
    SOURCE_CHALLENGER_DISAGREEMENT = "source_challenger_disagreement"
    FAILURE_CLASS = "failure_class"


_REPRESENTATIVE_ALLOWED_INPUTS = frozenset(
    {
        HoldoutSelectionInput.SOURCE_LIBRARY_ELIGIBILITY,
        HoldoutSelectionInput.SET_ROLE,
        HoldoutSelectionInput.DETERMINISTIC_SEED,
        HoldoutSelectionInput.BPM_STRATUM,
        HoldoutSelectionInput.STYLE_STRATUM,
        HoldoutSelectionInput.ENERGY_STRATUM,
    }
)


@dataclass(frozen=True, slots=True)
class DevelopmentEvidenceExclusionRegistry:
    registry_id: str
    registry_version: str
    case_ids: tuple[str, ...]
    scenario_fingerprints: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "registry_id", _non_empty(self.registry_id, "registry_id"))
        object.__setattr__(
            self,
            "registry_version",
            _non_empty(self.registry_version, "registry_version"),
        )
        case_ids = tuple(_non_empty(item, "development_case_id") for item in self.case_ids)
        scenarios = tuple(
            _non_empty(item, "development_scenario_fingerprint")
            for item in self.scenario_fingerprints
        )
        if not case_ids or not scenarios:
            raise ValueError("development exclusion registry must be non-empty")
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("development exclusion case_ids must be unique")
        if len(set(scenarios)) != len(scenarios):
            raise ValueError("development exclusion scenario_fingerprints must be unique")
        refs = tuple(_non_empty(item, "development_evidence_ref") for item in self.evidence_refs)
        if not refs:
            raise ValueError("development exclusion registry requires evidence refs")
        object.__setattr__(self, "case_ids", case_ids)
        object.__setattr__(self, "scenario_fingerprints", scenarios)
        object.__setattr__(self, "evidence_refs", refs)


@dataclass(frozen=True, slots=True)
class HoldoutSelectionBasis:
    basis_id: str
    basis_version: str
    selection_scope: SelectionScope
    selection_inputs: tuple[HoldoutSelectionInput, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "basis_id", _non_empty(self.basis_id, "basis_id"))
        object.__setattr__(self, "basis_version", _non_empty(self.basis_version, "basis_version"))
        inputs = tuple(self.selection_inputs)
        if not inputs or len(set(inputs)) != len(inputs):
            raise ValueError("selection_inputs must be non-empty and unique")
        if self.selection_scope is SelectionScope.REPRESENTATIVE_HOLDOUT:
            disallowed = tuple(item for item in inputs if item not in _REPRESENTATIVE_ALLOWED_INPUTS)
            if disallowed:
                names = ",".join(item.value for item in disallowed)
                raise ValueError(
                    f"representative holdout selection cannot depend on model outcomes: {names}"
                )
            if HoldoutSelectionInput.DETERMINISTIC_SEED not in inputs:
                raise ValueError("representative holdout selection must bind deterministic_seed")
        refs = tuple(_non_empty(item, "selection_basis_evidence_ref") for item in self.evidence_refs)
        if not refs:
            raise ValueError("holdout selection basis requires evidence refs")
        object.__setattr__(self, "selection_inputs", inputs)
        object.__setattr__(self, "evidence_refs", refs)


@dataclass(frozen=True, slots=True)
class CurationAssignmentBatchManifest:
    batch_id: str
    batch_version: str
    assignment_seed_commitment: str
    reviewer_refs: tuple[str, ...]
    case_ids: tuple[str, ...]
    assignment_fingerprints: tuple[str, ...]
    generated_at: str
    algorithm_identity_hidden: bool = True
    activation_authorized: bool = False
    personal_dj_model_training_authorized: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "batch_id",
            "batch_version",
            "assignment_seed_commitment",
            "generated_at",
        ):
            object.__setattr__(self, field_name, _non_empty(getattr(self, field_name), field_name))
        if self.batch_version != HOLDOUT_GUARD_VERSION:
            raise ValueError("unsupported assignment batch version")
        reviewers = tuple(_non_empty(item, "reviewer_ref") for item in self.reviewer_refs)
        cases = tuple(_non_empty(item, "case_id") for item in self.case_ids)
        fingerprints = tuple(
            _non_empty(item, "assignment_fingerprint") for item in self.assignment_fingerprints
        )
        if not reviewers or len(set(reviewers)) != len(reviewers):
            raise ValueError("reviewer_refs must be non-empty and unique")
        if not cases or len(set(cases)) != len(cases):
            raise ValueError("case_ids must be non-empty and unique")
        expected = len(reviewers) * len(cases)
        if len(fingerprints) != expected or len(set(fingerprints)) != expected:
            raise ValueError("assignment_fingerprints must cover reviewer x case exactly once")
        object.__setattr__(self, "reviewer_refs", reviewers)
        object.__setattr__(self, "case_ids", cases)
        object.__setattr__(self, "assignment_fingerprints", fingerprints)
        if not self.algorithm_identity_hidden:
            raise ValueError("assignment batch requires algorithm identity hiding")
        if self.activation_authorized:
            raise ValueError("assignment batch cannot authorize optimizer activation")
        if self.personal_dj_model_training_authorized:
            raise ValueError("assignment batch cannot authorize Personal DJ Model training")


__all__ = [
    "HOLDOUT_GUARD_VERSION",
    "CurationAssignmentBatchManifest",
    "DevelopmentEvidenceExclusionRegistry",
    "HoldoutSelectionBasis",
    "HoldoutSelectionInput",
]
