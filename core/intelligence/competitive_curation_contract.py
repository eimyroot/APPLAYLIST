from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

COMPETITIVE_CURATION_CONTRACT_VERSION = "competitive-curation-r1"


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


def _non_negative(value: float | None, field_name: str) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0.0:
        raise ValueError(f"{field_name} must be finite and non-negative")
    return numeric


class CompetitiveCurationStatus(StrEnum):
    COMPETITIVE = "competitive"
    INSUFFICIENT = "insufficient"
    NOT_PROVEN_MISSING_EVIDENCE = "not_proven_missing_evidence"


class ShadowPathPreference(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    TIE = "tie"
    NOT_PROVEN = "not_proven"


@dataclass(frozen=True, slots=True)
class TrackCurationEvidence:
    """Bounded track evidence for whole-set curation assessment.

    `vocal_presence` is intentionally optional. R1 never infers vocal presence from
    unrelated acoustic features; it may only be populated by explicit evidence.
    """

    track_id: str
    style_tags: tuple[str, ...] | None
    baseline_energy: float | None
    percussive_ratio: float | None
    harmonic_ratio: float | None
    beat_stability: float | None
    phrase_boundary_density_per_minute: float | None
    structural_label_diversity: float | None
    vocal_presence: float | None = None
    analysis_revision: str | None = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "track_id", _non_empty(self.track_id, "track_id"))
        if self.style_tags is not None:
            tags = tuple(
                dict.fromkeys(
                    str(item).strip().lower()
                    for item in self.style_tags
                    if str(item).strip()
                )
            )
            object.__setattr__(self, "style_tags", tags or None)
        for field_name in (
            "baseline_energy",
            "percussive_ratio",
            "harmonic_ratio",
            "beat_stability",
            "structural_label_diversity",
            "vocal_presence",
        ):
            object.__setattr__(self, field_name, _unit(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "phrase_boundary_density_per_minute",
            _non_negative(
                self.phrase_boundary_density_per_minute,
                "phrase_boundary_density_per_minute",
            ),
        )
        if self.analysis_revision is not None:
            object.__setattr__(
                self,
                "analysis_revision",
                _non_empty(self.analysis_revision, "analysis_revision"),
            )
        refs = tuple(str(item).strip() for item in self.evidence_refs if str(item).strip())
        if not refs:
            raise ValueError("evidence_refs must not be empty")
        object.__setattr__(self, "evidence_refs", refs)


@dataclass(frozen=True, slots=True)
class CompetitiveCurationPolicy:
    policy_id: str = "competitive-curation-shadow"
    policy_version: str = COMPETITIVE_CURATION_CONTRACT_VERSION
    style_target_weight: float = 2.0
    style_continuity_weight: float = 1.25
    energy_trajectory_weight: float = 2.0
    texture_groove_weight: float = 1.0
    structure_readiness_weight: float = 0.75
    contrast_control_weight: float = 1.25
    saturation_control_weight: float = 1.25
    evidence_completeness_weight: float = 1.0
    max_effective_energy_tolerance: float = 0.18
    minimum_adjacent_style_overlap: float = 0.25
    maximum_unexplained_contrast_fraction: float = 0.25
    maximum_non_target_run_fraction: float = 0.50
    minimum_energy_trajectory_fit: float = 0.65
    minimum_competitive_score: float = 0.68
    minimum_pairwise_delta: float = 0.05
    require_complete_style_evidence: bool = True
    require_complete_energy_evidence: bool = True
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _non_empty(self.policy_id, "policy_id"))
        object.__setattr__(
            self,
            "policy_version",
            _non_empty(self.policy_version, "policy_version"),
        )
        weight_names = (
            "style_target_weight",
            "style_continuity_weight",
            "energy_trajectory_weight",
            "texture_groove_weight",
            "structure_readiness_weight",
            "contrast_control_weight",
            "saturation_control_weight",
            "evidence_completeness_weight",
        )
        total = 0.0
        for field_name in weight_names:
            value = float(getattr(self, field_name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{field_name} must be finite and non-negative")
            object.__setattr__(self, field_name, value)
            total += value
        if total <= 0.0:
            raise ValueError("at least one competitive curation weight must be positive")
        for field_name in (
            "max_effective_energy_tolerance",
            "minimum_adjacent_style_overlap",
            "maximum_unexplained_contrast_fraction",
            "maximum_non_target_run_fraction",
            "minimum_energy_trajectory_fit",
            "minimum_competitive_score",
            "minimum_pairwise_delta",
        ):
            object.__setattr__(self, field_name, _unit(getattr(self, field_name), field_name))
        if self.activation_authorized:
            raise ValueError("competitive curation R1 is shadow-only and cannot authorize activation")


@dataclass(frozen=True, slots=True)
class PathCurationAssessment:
    path_id: str
    source_rank: int
    score: float | None
    status: CompetitiveCurationStatus
    component_scores: tuple[tuple[str, float | None], ...]
    evidence_completeness: float
    non_target_run_fraction: float | None
    unexplained_contrast_fraction: float | None
    missing_style_track_ids: tuple[str, ...]
    missing_energy_track_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    source_identity_preserved: bool = True
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_id", _non_empty(self.path_id, "path_id"))
        if self.source_rank <= 0:
            raise ValueError("source_rank must be positive")
        object.__setattr__(self, "score", _unit(self.score, "score"))
        object.__setattr__(
            self,
            "evidence_completeness",
            _unit(self.evidence_completeness, "evidence_completeness"),
        )
        object.__setattr__(
            self,
            "non_target_run_fraction",
            _unit(self.non_target_run_fraction, "non_target_run_fraction"),
        )
        object.__setattr__(
            self,
            "unexplained_contrast_fraction",
            _unit(self.unexplained_contrast_fraction, "unexplained_contrast_fraction"),
        )
        normalized_components: list[tuple[str, float | None]] = []
        names: set[str] = set()
        for name, value in self.component_scores:
            normalized_name = _non_empty(name, "component_name")
            if normalized_name in names:
                raise ValueError("component score names must be unique")
            names.add(normalized_name)
            normalized_components.append((normalized_name, _unit(value, normalized_name)))
        object.__setattr__(self, "component_scores", tuple(normalized_components))
        object.__setattr__(self, "missing_style_track_ids", tuple(self.missing_style_track_ids))
        object.__setattr__(self, "missing_energy_track_ids", tuple(self.missing_energy_track_ids))
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))
        if not self.source_identity_preserved:
            raise ValueError("shadow curation must preserve source path identity")
        if self.activation_authorized:
            raise ValueError("shadow curation assessment cannot authorize activation")


@dataclass(frozen=True, slots=True)
class ShadowPathComparison:
    left_path_id: str
    right_path_id: str
    left_score: float | None
    right_score: float | None
    right_minus_left: float | None
    preference: ShadowPathPreference
    reason_codes: tuple[str, ...]
    activation_authorized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "left_path_id", _non_empty(self.left_path_id, "left_path_id"))
        object.__setattr__(self, "right_path_id", _non_empty(self.right_path_id, "right_path_id"))
        if self.left_path_id == self.right_path_id:
            raise ValueError("shadow comparison requires distinct path ids")
        object.__setattr__(self, "left_score", _unit(self.left_score, "left_score"))
        object.__setattr__(self, "right_score", _unit(self.right_score, "right_score"))
        if self.right_minus_left is not None:
            delta = float(self.right_minus_left)
            if not math.isfinite(delta) or not -1.0 <= delta <= 1.0:
                raise ValueError("right_minus_left must be between -1 and 1")
            object.__setattr__(self, "right_minus_left", delta)
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(self.reason_codes)))
        if self.activation_authorized:
            raise ValueError("shadow comparison cannot authorize activation")


__all__ = [
    "COMPETITIVE_CURATION_CONTRACT_VERSION",
    "CompetitiveCurationPolicy",
    "CompetitiveCurationStatus",
    "PathCurationAssessment",
    "ShadowPathComparison",
    "ShadowPathPreference",
    "TrackCurationEvidence",
]
