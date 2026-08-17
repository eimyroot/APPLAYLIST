from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from core.intelligence.transition_contract import TransitionAssessment, TransitionStrategy

SET_INTELLIGENCE_CONTRACT_VERSION = "set-intelligence-v1"
SET_RANKING_POLICY_VERSION = "set-ranking-v1"


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


def _positive(value: float | None, field_name: str) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or numeric <= 0.0:
        raise ValueError(f"{field_name} must be finite and positive")
    return numeric


class SetGoal(StrEnum):
    WARM_UP = "warm_up"
    CLUB_FLOW = "club_flow"
    FESTIVAL_ARC = "festival_arc"
    PEAK_TIME = "peak_time"
    AFTERHOURS = "afterhours"
    CLOSING = "closing"
    STYLE_BRIDGE = "style_bridge"
    CUSTOM = "custom"


class SetPhaseType(StrEnum):
    INTRO = "intro"
    WARMUP = "warmup"
    GROOVE = "groove"
    LIFT = "lift"
    PEAK = "peak"
    AFTERGLOW = "afterglow"
    CLOSING = "closing"
    CUSTOM = "custom"


class CandidateEligibility(StrEnum):
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"


class MissingFeaturePolicy(StrEnum):
    EXCLUDE_AND_RENORMALIZE = "exclude_and_renormalize"
    UNCERTAINTY_PENALTY = "uncertainty_penalty"
    HARD_BLOCK = "hard_block"


@dataclass(frozen=True, slots=True)
class RangeBand:
    minimum: float
    maximum: float

    def __post_init__(self) -> None:
        minimum = float(self.minimum)
        maximum = float(self.maximum)
        if not math.isfinite(minimum) or not math.isfinite(maximum) or maximum < minimum:
            raise ValueError("range band must satisfy finite minimum <= maximum")
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)

    def fit(self, value: float | None) -> float | None:
        if value is None:
            return None
        numeric = float(value)
        if not math.isfinite(numeric):
            return None
        if self.minimum <= numeric <= self.maximum:
            return 1.0
        span = max(1.0, self.maximum - self.minimum)
        distance = min(abs(numeric - self.minimum), abs(numeric - self.maximum))
        return max(0.0, 1.0 - distance / span)


@dataclass(frozen=True, slots=True)
class EnergyControlPoint:
    normalized_set_position: float
    target_energy: float
    tolerance: float
    phase_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "normalized_set_position",
            _unit(self.normalized_set_position, "normalized_set_position"),
        )
        object.__setattr__(self, "target_energy", _unit(self.target_energy, "target_energy"))
        tolerance = float(self.tolerance)
        if not math.isfinite(tolerance) or tolerance < 0.0 or tolerance > 1.0:
            raise ValueError("energy tolerance must be between 0 and 1")
        object.__setattr__(self, "tolerance", tolerance)
        if self.phase_id is not None:
            object.__setattr__(self, "phase_id", _non_empty(self.phase_id, "phase_id"))


@dataclass(frozen=True, slots=True)
class EnergyTrajectory:
    trajectory_id: str
    trajectory_version: str
    control_points: tuple[EnergyControlPoint, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "trajectory_id", _non_empty(self.trajectory_id, "trajectory_id"))
        object.__setattr__(
            self,
            "trajectory_version",
            _non_empty(self.trajectory_version, "trajectory_version"),
        )
        points = tuple(self.control_points)
        if not points:
            raise ValueError("energy trajectory requires at least one control point")
        positions = tuple(item.normalized_set_position for item in points)
        if positions != tuple(sorted(positions)):
            raise ValueError("energy control points must be ordered")
        if len(set(positions)) != len(positions):
            raise ValueError("energy control point positions must be unique")
        object.__setattr__(self, "control_points", points)

    def target_at(self, position: float) -> tuple[float, float]:
        normalized = _unit(position, "set position")
        assert normalized is not None
        points = self.control_points
        if normalized <= points[0].normalized_set_position:
            return points[0].target_energy, points[0].tolerance
        if normalized >= points[-1].normalized_set_position:
            return points[-1].target_energy, points[-1].tolerance
        for left, right in zip(points, points[1:]):
            if left.normalized_set_position <= normalized <= right.normalized_set_position:
                span = right.normalized_set_position - left.normalized_set_position
                ratio = (normalized - left.normalized_set_position) / span
                target = left.target_energy + ratio * (right.target_energy - left.target_energy)
                tolerance = left.tolerance + ratio * (right.tolerance - left.tolerance)
                return target, tolerance
        raise RuntimeError("unreachable energy trajectory state")


@dataclass(frozen=True, slots=True)
class EligibleLibraryScope:
    scope_revision: str
    explicit_track_ids: tuple[str, ...] | None = None
    include_tags: tuple[str, ...] = ()
    exclude_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "scope_revision", _non_empty(self.scope_revision, "scope_revision")
        )
        if self.explicit_track_ids is not None:
            object.__setattr__(
                self,
                "explicit_track_ids",
                tuple(_non_empty(item, "track_id") for item in self.explicit_track_ids),
            )
        object.__setattr__(
            self, "include_tags", tuple(_non_empty(item, "include_tag") for item in self.include_tags)
        )
        object.__setattr__(
            self, "exclude_tags", tuple(_non_empty(item, "exclude_tag") for item in self.exclude_tags)
        )


@dataclass(frozen=True, slots=True)
class LockedPosition:
    track_id: str
    lock_version: str
    position_index: int | None = None
    segment_id: str | None = None
    transition_strategy: TransitionStrategy | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "track_id", _non_empty(self.track_id, "track_id"))
        object.__setattr__(self, "lock_version", _non_empty(self.lock_version, "lock_version"))
        if self.position_index is not None and self.position_index < 0:
            raise ValueError("position_index must be non-negative")
        if self.segment_id is not None:
            object.__setattr__(self, "segment_id", _non_empty(self.segment_id, "segment_id"))


@dataclass(frozen=True, slots=True)
class SetPhase:
    phase_id: str
    phase_type: SetPhaseType
    ordinal: int
    target_fraction_start: float
    target_fraction_end: float
    explanation_label: str
    target_energy_band: RangeBand | None = None
    target_tempo_band: RangeBand | None = None
    style_targets: tuple[str, ...] = ()
    style_avoid: tuple[str, ...] = ()
    preferred_transition_strategies: tuple[TransitionStrategy, ...] = ()
    forbidden_transition_strategies: tuple[TransitionStrategy, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "phase_id", _non_empty(self.phase_id, "phase_id"))
        if self.ordinal < 0:
            raise ValueError("phase ordinal must be non-negative")
        start = _unit(self.target_fraction_start, "target_fraction_start")
        end = _unit(self.target_fraction_end, "target_fraction_end")
        assert start is not None and end is not None
        if end <= start:
            raise ValueError("phase target fraction must satisfy start < end")
        object.__setattr__(self, "target_fraction_start", start)
        object.__setattr__(self, "target_fraction_end", end)
        object.__setattr__(
            self, "explanation_label", _non_empty(self.explanation_label, "explanation_label")
        )
        object.__setattr__(self, "style_targets", tuple(self.style_targets))
        object.__setattr__(self, "style_avoid", tuple(self.style_avoid))
        object.__setattr__(
            self, "preferred_transition_strategies", tuple(self.preferred_transition_strategies)
        )
        object.__setattr__(
            self, "forbidden_transition_strategies", tuple(self.forbidden_transition_strategies)
        )


@dataclass(frozen=True, slots=True)
class PlaylistIntent:
    intent_id: str
    intent_version: str
    goal: SetGoal
    eligible_library_scope: EligibleLibraryScope
    phase_plan: tuple[SetPhase, ...]
    energy_trajectory: EnergyTrajectory
    target_duration_seconds: float | None = None
    target_track_count: int | None = None
    required_track_ids: tuple[str, ...] = ()
    forbidden_track_ids: tuple[str, ...] = ()
    locked_positions: tuple[LockedPosition, ...] = ()
    allow_track_repeats: bool = False
    duration_tolerance_seconds: float = 0.0
    reject_critical_warnings: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "intent_id", _non_empty(self.intent_id, "intent_id"))
        object.__setattr__(self, "intent_version", _non_empty(self.intent_version, "intent_version"))
        object.__setattr__(
            self,
            "target_duration_seconds",
            _positive(self.target_duration_seconds, "target_duration_seconds"),
        )
        if self.target_track_count is not None and self.target_track_count <= 0:
            raise ValueError("target_track_count must be positive")
        tolerance = float(self.duration_tolerance_seconds)
        if not math.isfinite(tolerance) or tolerance < 0.0:
            raise ValueError("duration_tolerance_seconds must be finite and non-negative")
        object.__setattr__(self, "duration_tolerance_seconds", tolerance)
        required = tuple(_non_empty(item, "required_track_id") for item in self.required_track_ids)
        forbidden = tuple(_non_empty(item, "forbidden_track_id") for item in self.forbidden_track_ids)
        if set(required) & set(forbidden):
            raise ValueError("required and forbidden tracks must not overlap")
        object.__setattr__(self, "required_track_ids", required)
        object.__setattr__(self, "forbidden_track_ids", forbidden)
        object.__setattr__(self, "locked_positions", tuple(self.locked_positions))
        phases = tuple(self.phase_plan)
        if not phases:
            raise ValueError("phase_plan must not be empty")
        ordinals = tuple(item.ordinal for item in phases)
        if ordinals != tuple(sorted(ordinals)):
            raise ValueError("phase_plan must be ordered by ordinal")
        if len(set(ordinals)) != len(ordinals):
            raise ValueError("phase ordinals must be unique")
        phase_ids = tuple(item.phase_id for item in phases)
        if len(set(phase_ids)) != len(phase_ids):
            raise ValueError("phase ids must be unique")
        for previous, current in zip(phases, phases[1:]):
            if current.target_fraction_start < previous.target_fraction_end:
                raise ValueError("phase target fractions must not overlap")
        object.__setattr__(self, "phase_plan", phases)

    def phase(self, phase_id: str) -> SetPhase:
        for phase in self.phase_plan:
            if phase.phase_id == phase_id:
                return phase
        raise KeyError("unknown set phase")


@dataclass(frozen=True, slots=True)
class PlaylistContext:
    context_id: str
    context_version: str
    current_phase_id: str
    current_position_index: int
    elapsed_duration_seconds: float
    phase_progress: float
    current_track_id: str | None = None
    current_segment_id: str | None = None
    current_energy_state: float | None = None
    remaining_duration_seconds: float | None = None
    remaining_track_count: int | None = None
    context_evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "context_id", _non_empty(self.context_id, "context_id"))
        object.__setattr__(
            self, "context_version", _non_empty(self.context_version, "context_version")
        )
        object.__setattr__(
            self, "current_phase_id", _non_empty(self.current_phase_id, "current_phase_id")
        )
        if self.current_position_index < 0:
            raise ValueError("current_position_index must be non-negative")
        elapsed = float(self.elapsed_duration_seconds)
        if not math.isfinite(elapsed) or elapsed < 0.0:
            raise ValueError("elapsed_duration_seconds must be finite and non-negative")
        object.__setattr__(self, "elapsed_duration_seconds", elapsed)
        object.__setattr__(self, "phase_progress", _unit(self.phase_progress, "phase_progress"))
        object.__setattr__(
            self,
            "current_energy_state",
            _unit(self.current_energy_state, "current_energy_state"),
        )
        if self.remaining_duration_seconds is not None:
            remaining = float(self.remaining_duration_seconds)
            if not math.isfinite(remaining) or remaining < 0.0:
                raise ValueError("remaining_duration_seconds must be finite and non-negative")
            object.__setattr__(self, "remaining_duration_seconds", remaining)
        if self.remaining_track_count is not None and self.remaining_track_count < 0:
            raise ValueError("remaining_track_count must be non-negative")
        if (self.current_track_id is None) != (self.current_segment_id is None):
            raise ValueError("current track and segment must both be present or absent")
        object.__setattr__(self, "context_evidence_refs", tuple(self.context_evidence_refs))


@dataclass(frozen=True, slots=True)
class SetStep:
    order_index: int
    track_id: str
    segment_id: str
    phase_id: str
    incoming_transition_id: str | None = None
    chosen_strategy: TransitionStrategy | None = None
    local_projection_score: float | None = None
    explanation_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.order_index < 0:
            raise ValueError("order_index must be non-negative")
        for name in ("track_id", "segment_id", "phase_id"):
            object.__setattr__(self, name, _non_empty(getattr(self, name), name))
        object.__setattr__(
            self, "local_projection_score", _unit(self.local_projection_score, "local_projection_score")
        )
        object.__setattr__(self, "explanation_codes", tuple(self.explanation_codes))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class SequenceState:
    state_id: str
    state_version: str
    selected_steps: tuple[SetStep, ...]
    current_track_id: str | None
    current_segment_id: str | None
    used_track_ids: tuple[str, ...]
    cumulative_duration_seconds: float
    current_energy_state: float | None
    satisfied_required_track_ids: tuple[str, ...] = ()
    remaining_required_track_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_id", _non_empty(self.state_id, "state_id"))
        object.__setattr__(self, "state_version", _non_empty(self.state_version, "state_version"))
        steps = tuple(self.selected_steps)
        if tuple(step.order_index for step in steps) != tuple(range(len(steps))):
            raise ValueError("selected step order must be contiguous from zero")
        if (self.current_track_id is None) != (self.current_segment_id is None):
            raise ValueError("current track and segment must both be present or absent")
        if steps:
            if self.current_track_id != steps[-1].track_id or self.current_segment_id != steps[-1].segment_id:
                raise ValueError("current track/segment must match final selected step")
        elif self.current_track_id is not None:
            raise ValueError("empty sequence state must not have a current track")
        used = tuple(self.used_track_ids)
        if steps and used != tuple(step.track_id for step in steps):
            raise ValueError("used_track_ids must exactly follow selected steps")
        duration = float(self.cumulative_duration_seconds)
        if not math.isfinite(duration) or duration < 0.0:
            raise ValueError("cumulative_duration_seconds must be finite and non-negative")
        object.__setattr__(self, "cumulative_duration_seconds", duration)
        object.__setattr__(
            self, "current_energy_state", _unit(self.current_energy_state, "current_energy_state")
        )
        object.__setattr__(self, "selected_steps", steps)
        object.__setattr__(self, "used_track_ids", used)
        object.__setattr__(
            self, "satisfied_required_track_ids", tuple(self.satisfied_required_track_ids)
        )
        object.__setattr__(
            self, "remaining_required_track_ids", tuple(self.remaining_required_track_ids)
        )
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class CandidateDescriptor:
    transition: TransitionAssessment
    target_duration_seconds: float
    style_tags: tuple[str, ...] | None = None
    critical_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "target_duration_seconds",
            _positive(self.target_duration_seconds, "target_duration_seconds"),
        )
        if self.style_tags is not None:
            object.__setattr__(
                self, "style_tags", tuple(sorted(set(str(item).strip() for item in self.style_tags if str(item).strip())))
            )
        object.__setattr__(self, "critical_warnings", tuple(sorted(set(self.critical_warnings))))


@dataclass(frozen=True, slots=True)
class SetCandidateFeatures:
    transition_quality: float | None
    phase_fit: float | None
    energy_trajectory_fit: float | None
    tempo_trajectory_fit: float | None
    harmonic_policy_fit: float | None
    style_fit: float | None
    novelty_fit: float | None
    artist_spacing_fit: float | None
    required_track_progress: float | None
    duration_fit: float | None
    future_feasibility: float | None
    uncertainty_penalty: float | None

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            object.__setattr__(self, field_name, _unit(getattr(self, field_name), field_name))


@dataclass(frozen=True, slots=True)
class SetRankingPolicy:
    ranking_policy_id: str
    ranking_policy_version: str
    feature_weights: tuple[tuple[str, float], ...]
    missing_feature_policy: MissingFeaturePolicy = MissingFeaturePolicy.EXCLUDE_AND_RENORMALIZE
    uncertainty_penalty_multiplier: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "ranking_policy_id", _non_empty(self.ranking_policy_id, "ranking_policy_id")
        )
        object.__setattr__(
            self,
            "ranking_policy_version",
            _non_empty(self.ranking_policy_version, "ranking_policy_version"),
        )
        known = set(SetCandidateFeatures.__dataclass_fields__)
        normalized: list[tuple[str, float]] = []
        seen: set[str] = set()
        for name, raw_weight in self.feature_weights:
            if name not in known:
                raise ValueError(f"unknown set candidate feature weight: {name}")
            if name in seen:
                raise ValueError(f"duplicate set candidate feature weight: {name}")
            weight = float(raw_weight)
            if not math.isfinite(weight) or weight < 0.0:
                raise ValueError("feature weights must be finite and non-negative")
            seen.add(name)
            normalized.append((name, weight))
        if not normalized or sum(weight for _, weight in normalized) <= 0.0:
            raise ValueError("at least one positive feature weight is required")
        penalty = float(self.uncertainty_penalty_multiplier)
        if not math.isfinite(penalty) or penalty < 0.0:
            raise ValueError("uncertainty_penalty_multiplier must be finite and non-negative")
        object.__setattr__(self, "feature_weights", tuple(normalized))
        object.__setattr__(self, "uncertainty_penalty_multiplier", penalty)

    def weight_for(self, feature_name: str) -> float:
        return dict(self.feature_weights).get(feature_name, 0.0)


@dataclass(frozen=True, slots=True)
class SequenceStatePreview:
    next_position_index: int
    target_track_id: str
    target_segment_id: str
    cumulative_duration_seconds: float
    remaining_required_track_ids: tuple[str, ...]
    phase_id: str

    def __post_init__(self) -> None:
        if self.next_position_index < 0:
            raise ValueError("next_position_index must be non-negative")
        object.__setattr__(self, "target_track_id", _non_empty(self.target_track_id, "target_track_id"))
        object.__setattr__(
            self, "target_segment_id", _non_empty(self.target_segment_id, "target_segment_id")
        )
        object.__setattr__(self, "phase_id", _non_empty(self.phase_id, "phase_id"))
        duration = float(self.cumulative_duration_seconds)
        if not math.isfinite(duration) or duration < 0.0:
            raise ValueError("preview duration must be finite and non-negative")
        object.__setattr__(self, "cumulative_duration_seconds", duration)
        object.__setattr__(
            self, "remaining_required_track_ids", tuple(self.remaining_required_track_ids)
        )


@dataclass(frozen=True, slots=True)
class SetCandidate:
    candidate_id: str
    target_track_id: str
    target_segment_id: str
    transition_assessment_id: str
    transition_context_id: str
    phase_id: str
    eligibility: CandidateEligibility
    blocked_reasons: tuple[str, ...]
    feature_vector: SetCandidateFeatures
    score: float | None
    confidence: float | None
    rank: int | None
    explanation_codes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    resulting_state_preview: SequenceStatePreview

    def __post_init__(self) -> None:
        for name in (
            "candidate_id",
            "target_track_id",
            "target_segment_id",
            "transition_assessment_id",
            "transition_context_id",
            "phase_id",
        ):
            object.__setattr__(self, name, _non_empty(getattr(self, name), name))
        object.__setattr__(self, "score", _unit(self.score, "candidate score"))
        object.__setattr__(self, "confidence", _unit(self.confidence, "candidate confidence"))
        blocked = tuple(self.blocked_reasons)
        if self.eligibility is CandidateEligibility.BLOCKED:
            if not blocked:
                raise ValueError("blocked candidate requires blocked_reasons")
            if self.score is not None or self.rank is not None:
                raise ValueError("blocked candidate must not carry score or rank")
        elif blocked:
            raise ValueError("eligible candidate must not carry blocked_reasons")
        if self.rank is not None and self.rank <= 0:
            raise ValueError("rank must be positive")
        object.__setattr__(self, "blocked_reasons", blocked)
        object.__setattr__(self, "explanation_codes", tuple(self.explanation_codes))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class CandidateSet:
    candidate_set_id: str
    input_fingerprint: str
    intent_ref: tuple[str, str]
    context_ref: tuple[str, str]
    sequence_state_ref: tuple[str, str]
    transition_policy_ref: str
    ranking_policy_ref: tuple[str, str]
    eligible_candidates: tuple[SetCandidate, ...]
    rejected_candidates: tuple[SetCandidate, ...]
    generated_at: str
    deterministic_ordering: bool
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "candidate_set_id", _non_empty(self.candidate_set_id, "candidate_set_id")
        )
        object.__setattr__(
            self, "input_fingerprint", _non_empty(self.input_fingerprint, "input_fingerprint")
        )
        object.__setattr__(self, "generated_at", _non_empty(self.generated_at, "generated_at"))
        if not self.transition_policy_ref.strip():
            raise ValueError("transition_policy_ref must not be empty")
        eligible = tuple(self.eligible_candidates)
        expected_ranks = tuple(range(1, len(eligible) + 1))
        if tuple(item.rank for item in eligible) != expected_ranks:
            raise ValueError("eligible candidate ranks must be contiguous from one")
        object.__setattr__(self, "eligible_candidates", eligible)
        object.__setattr__(self, "rejected_candidates", tuple(self.rejected_candidates))
        object.__setattr__(self, "warnings", tuple(self.warnings))


__all__ = [
    "CandidateDescriptor",
    "CandidateEligibility",
    "CandidateSet",
    "EligibleLibraryScope",
    "EnergyControlPoint",
    "EnergyTrajectory",
    "LockedPosition",
    "MissingFeaturePolicy",
    "PlaylistContext",
    "PlaylistIntent",
    "RangeBand",
    "SequenceState",
    "SequenceStatePreview",
    "SetCandidate",
    "SetCandidateFeatures",
    "SetGoal",
    "SetPhase",
    "SetPhaseType",
    "SetRankingPolicy",
    "SetStep",
    "SET_INTELLIGENCE_CONTRACT_VERSION",
    "SET_RANKING_POLICY_VERSION",
]
