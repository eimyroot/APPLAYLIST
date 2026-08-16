from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from core.intelligence.music_dna import Confidence

TRANSITION_ASSESSMENT_VERSION = "transition-assessment-v1"
TRANSITION_POLICY_VERSION = "transition-policy-v1"


def _score(value: float | None, field_name: str) -> float | None:
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


class TransitionStrategy(StrEnum):
    LONG_BLEND = "long_blend"
    SHORT_BLEND = "short_blend"
    EQ_BLEND = "eq_blend"
    BASS_SWAP = "bass_swap"
    CUT = "cut"
    DROP_SWAP = "drop_swap"
    BREAKDOWN_TRANSITION = "breakdown_transition"
    LOOP_TRANSITION = "loop_transition"
    TEMPO_BRIDGE = "tempo_bridge"
    HALF_DOUBLE_TIME_SWITCH = "half_double_time_switch"
    STEM_ASSISTED = "stem_assisted"
    DELIBERATE_CONTRAST = "deliberate_contrast"


class EnergyDirection(StrEnum):
    RISE = "rise"
    HOLD = "hold"
    FALL = "fall"
    CONTRAST = "contrast"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class TransitionIdentity:
    transition_id: str
    source_track_id: str
    source_segment_id: str
    target_track_id: str
    target_segment_id: str
    assessment_version: str
    policy_version: str
    music_dna_revision_refs: tuple[str, str]
    created_at: str

    def __post_init__(self) -> None:
        for field_name in (
            "transition_id",
            "source_track_id",
            "source_segment_id",
            "target_track_id",
            "target_segment_id",
            "assessment_version",
            "policy_version",
            "created_at",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} must not be empty")
            object.__setattr__(self, field_name, value)
        refs = tuple(str(item).strip() for item in self.music_dna_revision_refs)
        if len(refs) != 2 or any(not item for item in refs):
            raise ValueError("music_dna_revision_refs must contain source and target revisions")
        object.__setattr__(self, "music_dna_revision_refs", refs)


@dataclass(frozen=True, slots=True)
class TransitionCompatibility:
    tempo_fit: float | None
    beat_grid_fit: float | None
    phrase_fit: float | None
    harmonic_fit: float | None
    groove_continuity: float | None
    structural_fit: float | None
    timbral_fit: float | None = None
    melodic_fit: float | None = None
    semantic_fit: float | None = None

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            object.__setattr__(self, field_name, _score(getattr(self, field_name), field_name))


@dataclass(frozen=True, slots=True)
class TransitionRisk:
    bass_collision: float | None
    vocal_collision: float | None
    spectral_masking: float | None
    loudness_discontinuity: float | None
    harmonic_clash: float | None
    phrase_mismatch: float | None
    tempo_instability: float | None
    transient_overload: float | None
    uncertainty: float

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            value = _score(getattr(self, field_name), field_name)
            if value is None and field_name == "uncertainty":
                raise ValueError("uncertainty must be explicit")
            object.__setattr__(self, field_name, value)


@dataclass(frozen=True, slots=True)
class TransitionCost:
    tempo_change_percent: float | None
    time_stretch_cost: float | None
    pitch_shift_semitones: float | None
    key_shift_cost: float | None
    loop_dependency: bool
    stem_dependency: bool
    effect_dependency: bool
    preparation_complexity: float | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tempo_change_percent",
            _non_negative(self.tempo_change_percent, "tempo_change_percent"),
        )
        object.__setattr__(
            self,
            "pitch_shift_semitones",
            _non_negative(self.pitch_shift_semitones, "pitch_shift_semitones"),
        )
        for field_name in ("time_stretch_cost", "key_shift_cost", "preparation_complexity"):
            object.__setattr__(self, field_name, _score(getattr(self, field_name), field_name))


@dataclass(frozen=True, slots=True)
class TransitionEnergyEffect:
    source_energy_state: float | None
    target_energy_state: float | None
    delta: float | None
    local_curve_alignment: float | None
    direction: EnergyDirection
    confidence: Confidence

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_energy_state",
            _score(self.source_energy_state, "source_energy_state"),
        )
        object.__setattr__(
            self,
            "target_energy_state",
            _score(self.target_energy_state, "target_energy_state"),
        )
        object.__setattr__(
            self,
            "local_curve_alignment",
            _score(self.local_curve_alignment, "local_curve_alignment"),
        )
        if self.delta is not None:
            numeric = float(self.delta)
            if not math.isfinite(numeric) or not -1.0 <= numeric <= 1.0:
                raise ValueError("energy delta must be between -1 and 1")
            object.__setattr__(self, "delta", numeric)


@dataclass(frozen=True, slots=True)
class TransitionWindow:
    source_start_seconds: float
    source_end_seconds: float
    target_start_seconds: float
    target_end_seconds: float
    source_bar_count: int | None
    target_bar_count: int | None
    confidence: Confidence

    def __post_init__(self) -> None:
        for prefix in ("source", "target"):
            start = float(getattr(self, f"{prefix}_start_seconds"))
            end = float(getattr(self, f"{prefix}_end_seconds"))
            if not math.isfinite(start) or not math.isfinite(end) or start < 0.0 or end <= start:
                raise ValueError(f"{prefix} transition window must satisfy 0 <= start < end")
            object.__setattr__(self, f"{prefix}_start_seconds", start)
            object.__setattr__(self, f"{prefix}_end_seconds", end)
        for field_name in ("source_bar_count", "target_bar_count"):
            value = getattr(self, field_name)
            if value is not None and value <= 0:
                raise ValueError(f"{field_name} must be positive when present")


@dataclass(frozen=True, slots=True)
class TransitionStrategyCandidate:
    strategy: TransitionStrategy
    suitability: float
    required_capabilities: tuple[str, ...]
    explanation_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        suitability = _score(self.suitability, "strategy suitability")
        if suitability is None:
            raise ValueError("strategy suitability must be explicit")
        object.__setattr__(self, "suitability", suitability)
        object.__setattr__(self, "required_capabilities", tuple(self.required_capabilities))
        codes = tuple(code.strip() for code in self.explanation_codes if code.strip())
        if not codes:
            raise ValueError("strategy candidate requires explanation_codes")
        object.__setattr__(self, "explanation_codes", codes)


@dataclass(frozen=True, slots=True)
class TransitionWeights:
    tempo_fit: float = 1.0
    beat_grid_fit: float = 1.0
    phrase_fit: float = 1.0
    harmonic_fit: float = 1.0
    groove_continuity: float = 1.0
    structural_fit: float = 1.0
    risk_penalty: float = 1.0

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            value = float(getattr(self, field_name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{field_name} must be finite and non-negative")
            object.__setattr__(self, field_name, value)
        positive = sum(
            getattr(self, field_name)
            for field_name in self.__dataclass_fields__
            if field_name != "risk_penalty"
        )
        if positive <= 0.0:
            raise ValueError("at least one compatibility weight must be positive")


@dataclass(frozen=True, slots=True)
class TransitionContext:
    context_id: str
    context_version: str
    goal: str
    desired_energy_direction: EnergyDirection | None
    max_tempo_change_percent: float | None
    minimum_harmonic_fit: float | None
    require_phrase_evidence: bool
    allowed_strategies: tuple[TransitionStrategy, ...]
    weights: TransitionWeights

    def __post_init__(self) -> None:
        for field_name in ("context_id", "context_version", "goal"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} must not be empty")
            object.__setattr__(self, field_name, value)
        object.__setattr__(
            self,
            "max_tempo_change_percent",
            _non_negative(self.max_tempo_change_percent, "max_tempo_change_percent"),
        )
        object.__setattr__(
            self,
            "minimum_harmonic_fit",
            _score(self.minimum_harmonic_fit, "minimum_harmonic_fit"),
        )
        strategies = tuple(self.allowed_strategies)
        if not strategies:
            raise ValueError("allowed_strategies must not be empty")
        object.__setattr__(self, "allowed_strategies", strategies)


@dataclass(frozen=True, slots=True)
class ContextualTransitionProjection:
    context_id: str
    context_version: str
    score: float | None
    blocked_reasons: tuple[str, ...]
    rank_features: tuple[str, ...]
    confidence: Confidence
    explanation_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.context_id.strip() or not self.context_version.strip():
            raise ValueError("projection context identity must not be empty")
        object.__setattr__(self, "score", _score(self.score, "projection score"))
        blocked = tuple(item.strip() for item in self.blocked_reasons if item.strip())
        if blocked and self.score is not None:
            raise ValueError("blocked contextual projection must not carry a score")
        object.__setattr__(self, "blocked_reasons", blocked)
        object.__setattr__(self, "rank_features", tuple(self.rank_features))
        object.__setattr__(self, "explanation_codes", tuple(self.explanation_codes))


@dataclass(frozen=True, slots=True)
class TransitionExplanation:
    code: str
    severity: str
    dimension: str
    evidence_refs: tuple[str, ...]
    confidence: Confidence

    def __post_init__(self) -> None:
        for field_name in ("code", "severity", "dimension"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} must not be empty")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class TransitionAssessment:
    identity: TransitionIdentity
    compatibility_vector: TransitionCompatibility
    risk_vector: TransitionRisk
    cost_vector: TransitionCost
    energy_effect: TransitionEnergyEffect
    candidate_strategies: tuple[TransitionStrategyCandidate, ...]
    preferred_strategy: TransitionStrategy | None
    usable_window: TransitionWindow
    contextual_projection: ContextualTransitionProjection
    confidence: Confidence
    explanations: tuple[TransitionExplanation, ...]
    evidence_refs: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        strategies = tuple(self.candidate_strategies)
        if not strategies:
            raise ValueError("TransitionAssessment requires candidate strategies")
        if self.preferred_strategy is not None and self.preferred_strategy not in {
            item.strategy for item in strategies
        }:
            raise ValueError("preferred_strategy must be one of candidate_strategies")
        refs = tuple(item.strip() for item in self.evidence_refs if item.strip())
        if not refs:
            raise ValueError("TransitionAssessment requires evidence_refs")
        object.__setattr__(self, "candidate_strategies", strategies)
        object.__setattr__(self, "explanations", tuple(self.explanations))
        object.__setattr__(self, "evidence_refs", refs)
        object.__setattr__(self, "warnings", tuple(str(item) for item in self.warnings))


__all__ = [
    "ContextualTransitionProjection",
    "EnergyDirection",
    "TRANSITION_ASSESSMENT_VERSION",
    "TRANSITION_POLICY_VERSION",
    "TransitionAssessment",
    "TransitionCompatibility",
    "TransitionContext",
    "TransitionCost",
    "TransitionEnergyEffect",
    "TransitionExplanation",
    "TransitionIdentity",
    "TransitionRisk",
    "TransitionStrategy",
    "TransitionStrategyCandidate",
    "TransitionWeights",
    "TransitionWindow",
]
