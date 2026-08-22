from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from core.intelligence.set_optimizer_contract import SetPathAlternative

MEANINGFUL_DIVERSITY_CONTRACT_VERSION = "meaningful-diversity-style-energy-r1"


def _non_empty(value: str, field_name: str, *, maximum: int = 256) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    if len(normalized) > maximum:
        raise ValueError(f"{field_name} exceeds maximum length {maximum}")
    return normalized


def _unit(value: float | None, field_name: str) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return numeric


class MeaningfulDiversityStatus(StrEnum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT_MEANINGFUL_DIVERSITY = "insufficient_meaningful_diversity"
    NOT_PROVEN_MISSING_EVIDENCE = "not_proven_missing_evidence"


@dataclass(frozen=True, slots=True)
class TrackMusicalEvidence:
    track_id: str
    style_tags: tuple[str, ...] | None
    energy: float | None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "track_id", _non_empty(self.track_id, "track_id"))
        if self.style_tags is not None:
            tags = tuple(
                sorted(
                    {
                        _non_empty(item, "style_tag", maximum=128).lower()
                        for item in self.style_tags
                        if str(item).strip()
                    }
                )
            )
            if len(tags) > 32:
                raise ValueError("style_tags must contain at most 32 unique tags")
            object.__setattr__(self, "style_tags", tags)
        object.__setattr__(self, "energy", _unit(self.energy, "energy"))
        refs = tuple(_non_empty(item, "evidence_ref") for item in self.evidence_refs)
        if len(refs) > 64:
            raise ValueError("evidence_refs must contain at most 64 entries")
        object.__setattr__(self, "evidence_refs", refs)


@dataclass(frozen=True, slots=True)
class MeaningfulDiversityPolicy:
    policy_id: str = "meaningful-diversity-style-energy"
    policy_version: str = MEANINGFUL_DIVERSITY_CONTRACT_VERSION
    alternative_limit: int = 2
    minimum_meaningful_distance: float = 0.20
    minimum_style_coherence: float = 0.55
    minimum_energy_coherence: float = 0.55
    minimum_adjacent_style_overlap: float = 0.20
    maximum_style_drift_fraction: float = 0.35
    maximum_style_avoid_fraction: float = 0.0
    maximum_non_target_style_concentration: float = 0.60
    style_distance_weight: float = 0.60
    energy_distance_weight: float = 0.40
    require_complete_style_evidence: bool = True
    require_complete_energy_evidence: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _non_empty(self.policy_id, "policy_id"))
        object.__setattr__(
            self,
            "policy_version",
            _non_empty(self.policy_version, "policy_version"),
        )
        if not 2 <= self.alternative_limit <= 128:
            raise ValueError("alternative_limit must be between 2 and 128")
        for field_name in (
            "minimum_meaningful_distance",
            "minimum_style_coherence",
            "minimum_energy_coherence",
            "minimum_adjacent_style_overlap",
            "maximum_style_drift_fraction",
            "maximum_style_avoid_fraction",
            "maximum_non_target_style_concentration",
            "style_distance_weight",
            "energy_distance_weight",
        ):
            object.__setattr__(self, field_name, _unit(getattr(self, field_name), field_name))
        if self.style_distance_weight + self.energy_distance_weight <= 0.0:
            raise ValueError("at least one meaningful-distance weight must be positive")


@dataclass(frozen=True, slots=True)
class PathCoherenceAssessment:
    path_id: str
    source_rank: int
    style_coherence: float | None
    energy_coherence: float | None
    style_drift_fraction: float | None
    style_avoid_fraction: float | None
    non_target_style_concentration: float | None
    missing_style_track_ids: tuple[str, ...]
    missing_energy_track_ids: tuple[str, ...]
    coherence_pass: bool
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_id", _non_empty(self.path_id, "path_id"))
        if self.source_rank <= 0:
            raise ValueError("source_rank must be positive")
        for field_name in (
            "style_coherence",
            "energy_coherence",
            "style_drift_fraction",
            "style_avoid_fraction",
            "non_target_style_concentration",
        ):
            object.__setattr__(self, field_name, _unit(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "missing_style_track_ids",
            tuple(dict.fromkeys(self.missing_style_track_ids)),
        )
        object.__setattr__(
            self,
            "missing_energy_track_ids",
            tuple(dict.fromkeys(self.missing_energy_track_ids)),
        )
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))


@dataclass(frozen=True, slots=True)
class PairwiseMeaningfulDiversity:
    candidate_path_id: str
    reference_path_id: str
    technically_different: bool
    style_distance: float | None
    energy_distance: float | None
    meaningful_distance: float | None
    meaningful: bool
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_path_id",
            _non_empty(self.candidate_path_id, "candidate_path_id"),
        )
        object.__setattr__(
            self,
            "reference_path_id",
            _non_empty(self.reference_path_id, "reference_path_id"),
        )
        for field_name in ("style_distance", "energy_distance", "meaningful_distance"):
            object.__setattr__(self, field_name, _unit(getattr(self, field_name), field_name))
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))


@dataclass(frozen=True, slots=True)
class MeaningfulAlternativeDecision:
    path_id: str
    source_rank: int
    selected: bool
    coherence_pass: bool
    comparison_refs: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_id", _non_empty(self.path_id, "path_id"))
        if self.source_rank <= 0:
            raise ValueError("source_rank must be positive")
        object.__setattr__(self, "comparison_refs", tuple(self.comparison_refs))
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))


@dataclass(frozen=True, slots=True)
class MeaningfulDiversitySelection:
    selection_id: str
    source_result_id: str
    source_input_fingerprint: str
    policy_ref: tuple[str, str]
    status: MeaningfulDiversityStatus
    selected_alternatives: tuple[SetPathAlternative, ...]
    coherence_assessments: tuple[PathCoherenceAssessment, ...]
    pairwise_comparisons: tuple[PairwiseMeaningfulDiversity, ...]
    decisions: tuple[MeaningfulAlternativeDecision, ...]
    deterministic_ordering: bool = True
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "selection_id", _non_empty(self.selection_id, "selection_id"))
        object.__setattr__(
            self,
            "source_result_id",
            _non_empty(self.source_result_id, "source_result_id"),
        )
        object.__setattr__(
            self,
            "source_input_fingerprint",
            _non_empty(self.source_input_fingerprint, "source_input_fingerprint"),
        )
        selected = tuple(self.selected_alternatives)
        if selected and selected[0].rank != 1:
            raise ValueError("source rank #1 must be preserved as the first reference path")
        ranks = tuple(item.rank for item in selected)
        if ranks != tuple(sorted(ranks)):
            raise ValueError("selected alternatives must preserve source rank ordering")
        if self.activation_authorized:
            raise ValueError("meaningful diversity R1 is evidence-only and cannot authorize activation")
        object.__setattr__(self, "selected_alternatives", selected)
        object.__setattr__(self, "coherence_assessments", tuple(self.coherence_assessments))
        object.__setattr__(self, "pairwise_comparisons", tuple(self.pairwise_comparisons))
        object.__setattr__(self, "decisions", tuple(self.decisions))


__all__ = [
    "MEANINGFUL_DIVERSITY_CONTRACT_VERSION",
    "MeaningfulAlternativeDecision",
    "MeaningfulDiversityPolicy",
    "MeaningfulDiversitySelection",
    "MeaningfulDiversityStatus",
    "PairwiseMeaningfulDiversity",
    "PathCoherenceAssessment",
    "TrackMusicalEvidence",
]
