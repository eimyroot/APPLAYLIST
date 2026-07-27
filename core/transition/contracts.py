from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from math import isclose
from types import MappingProxyType
from typing import Any


def _bounded(value: float, low: float, high: float, field_name: str) -> float:
    numeric = float(value)
    if not low <= numeric <= high:
        raise ValueError(f"{field_name} must be between {low} and {high}")
    return numeric


def _required_text(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


# Preserve legacy Enum.__str__ behavior for downstream compatibility.
class TransitionClass(str, Enum):  # noqa: UP042
    SAFE = "safe"
    POSSIBLE = "possible"
    CREATIVE = "creative"
    RISKY = "risky"
    UNKNOWN = "unknown"


class TransitionProfile(str, Enum):  # noqa: UP042
    BALANCED = "balanced"
    LONG_MELODIC_OVERLAP = "long_melodic_overlap"
    SHORT_PERCUSSION = "short_percussion"
    CREATIVE_TENSION = "creative_tension"


class DimensionName(str, Enum):  # noqa: UP042
    PHRASE = "phrase"
    ENERGY = "energy"
    RHYTHM = "rhythm"
    TONAL = "tonal"
    TEMPO = "tempo"
    VOCAL_COLLISION = "vocal_collision"
    BASS_COLLISION = "bass_collision"
    STRATEGY_FIT = "strategy_fit"


class UserDecisionType(str, Enum):  # noqa: UP042
    ACCEPT = "accept"
    REJECT = "reject"
    PREVIEW = "preview"
    OVERRIDE = "override"
    UNDECIDED = "undecided"


@dataclass(frozen=True)
class FeatureEstimate:
    value: Any | None
    confidence: float | None
    provider: str = "unknown"
    analysis_version: str = "unknown"
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.confidence is not None:
            object.__setattr__(
                self,
                "confidence",
                _bounded(self.confidence, 0.0, 1.0, "confidence"),
            )
        object.__setattr__(self, "provider", _required_text(self.provider, "provider"))
        object.__setattr__(
            self,
            "analysis_version",
            _required_text(self.analysis_version, "analysis_version"),
        )
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True)
class DimensionAssessment:
    name: DimensionName
    score: float
    confidence: float
    weight: float
    contribution: float
    evidence_codes: tuple[str, ...]
    risk_codes: tuple[str, ...] = ()
    unavailable: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        score = _bounded(self.score, 0.0, 100.0, "score")
        confidence = _bounded(self.confidence, 0.0, 1.0, "confidence")
        weight = _bounded(self.weight, 0.0, 1.0, "weight")
        contribution = float(self.contribution)
        if not isclose(contribution, score * weight, abs_tol=1e-6):
            raise ValueError("contribution must equal score * weight")
        if self.unavailable and confidence != 0.0:
            raise ValueError("unavailable dimensions must have zero measured confidence")
        evidence_codes = tuple(
            str(code).strip()
            for code in self.evidence_codes
            if str(code).strip()
        )
        if not evidence_codes:
            raise ValueError("evidence_codes must not be empty")

        object.__setattr__(self, "score", score)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "weight", weight)
        object.__setattr__(self, "contribution", contribution)
        object.__setattr__(self, "evidence_codes", evidence_codes)
        object.__setattr__(self, "risk_codes", tuple(self.risk_codes))
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))


@dataclass(frozen=True)
class TransitionAnalysisResult:
    analysis_id: str
    track_a_id: str
    track_b_id: str
    profile: TransitionProfile
    dimensions: tuple[DimensionAssessment, ...]
    overall_score: float
    overall_confidence: float
    evidence_coverage: float
    critical_risks: tuple[str, ...]
    analysis_version: str = "transition-analysis-v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "analysis_id", _required_text(self.analysis_id, "analysis_id"))
        object.__setattr__(self, "track_a_id", _required_text(self.track_a_id, "track_a_id"))
        object.__setattr__(self, "track_b_id", _required_text(self.track_b_id, "track_b_id"))
        object.__setattr__(
            self,
            "analysis_version",
            _required_text(self.analysis_version, "analysis_version"),
        )
        dimensions = tuple(self.dimensions)
        names = [dimension.name for dimension in dimensions]
        if len(names) != len(set(names)):
            raise ValueError("dimension names must be unique")
        score = _bounded(self.overall_score, 0.0, 100.0, "overall_score")
        if not isclose(score, sum(d.contribution for d in dimensions), abs_tol=1e-3):
            raise ValueError("overall_score must equal the sum of dimension contributions")

        object.__setattr__(self, "dimensions", dimensions)
        object.__setattr__(self, "overall_score", score)
        object.__setattr__(
            self,
            "overall_confidence",
            _bounded(self.overall_confidence, 0.0, 1.0, "overall_confidence"),
        )
        object.__setattr__(
            self,
            "evidence_coverage",
            _bounded(self.evidence_coverage, 0.0, 1.0, "evidence_coverage"),
        )
        object.__setattr__(self, "critical_risks", tuple(self.critical_risks))


@dataclass(frozen=True)
class TransitionRecommendation:
    assessment_id: str
    classification: TransitionClass
    strategy_code: str
    overlap_beats: int | None
    instructions: tuple[str, ...]
    preview_required: bool
    recommendation_version: str = "transition-recommendation-v1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "assessment_id",
            _required_text(self.assessment_id, "assessment_id"),
        )
        object.__setattr__(
            self,
            "strategy_code",
            _required_text(self.strategy_code, "strategy_code"),
        )
        object.__setattr__(
            self,
            "recommendation_version",
            _required_text(self.recommendation_version, "recommendation_version"),
        )
        if self.overlap_beats is not None and self.overlap_beats <= 0:
            raise ValueError("overlap_beats must be positive when present")
        object.__setattr__(self, "instructions", tuple(self.instructions))


@dataclass(frozen=True)
class TransitionExplanation:
    assessment_id: str
    summary_code: str
    positive_reasons: tuple[str, ...]
    risk_reasons: tuple[str, ...]
    uncertainty_reasons: tuple[str, ...]
    explanation_version: str = "transition-explanation-v1"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "assessment_id",
            _required_text(self.assessment_id, "assessment_id"),
        )
        object.__setattr__(
            self,
            "summary_code",
            _required_text(self.summary_code, "summary_code"),
        )
        object.__setattr__(
            self,
            "explanation_version",
            _required_text(self.explanation_version, "explanation_version"),
        )
        object.__setattr__(self, "positive_reasons", tuple(self.positive_reasons))
        object.__setattr__(self, "risk_reasons", tuple(self.risk_reasons))
        object.__setattr__(self, "uncertainty_reasons", tuple(self.uncertainty_reasons))


@dataclass(frozen=True)
class TransitionAssessment:
    assessment_id: str
    analysis: TransitionAnalysisResult
    recommendation: TransitionRecommendation
    explanation: TransitionExplanation
    assessment_version: str = "transition-assessment-v1"

    def __post_init__(self) -> None:
        assessment_id = _required_text(self.assessment_id, "assessment_id")
        object.__setattr__(self, "assessment_id", assessment_id)
        object.__setattr__(
            self,
            "assessment_version",
            _required_text(self.assessment_version, "assessment_version"),
        )
        if self.recommendation.assessment_id != assessment_id:
            raise ValueError("recommendation assessment_id does not match assessment")
        if self.explanation.assessment_id != assessment_id:
            raise ValueError("explanation assessment_id does not match assessment")


@dataclass(frozen=True)
class UserTransitionDecision:
    assessment_id: str
    decision: UserDecisionType
    chosen_strategy_code: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "assessment_id",
            _required_text(self.assessment_id, "assessment_id"),
        )
