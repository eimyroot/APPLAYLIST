from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from core.intelligence.music_dna import (
    CalibrationState,
    Confidence,
    FactStatus,
    MusicDNARevision,
    MusicSegmentDNA,
)
from core.intelligence.transition_contract import (
    ContextualTransitionProjection,
    EnergyDirection,
    TRANSITION_ASSESSMENT_VERSION,
    TRANSITION_POLICY_VERSION,
    TransitionAssessment,
    TransitionCompatibility,
    TransitionContext,
    TransitionCost,
    TransitionEnergyEffect,
    TransitionExplanation,
    TransitionIdentity,
    TransitionRisk,
    TransitionStrategy,
    TransitionStrategyCandidate,
    TransitionWeights,
    TransitionWindow,
)

_CAMELOT_RE = re.compile(r"^(?P<number>[1-9]|1[0-2])(?P<letter>[AB])$")


@dataclass(frozen=True, slots=True)
class _TempoMatch:
    fit: float
    change_percent: float
    source_relation: str
    target_relation: str


def preserve_groove_context_v1() -> TransitionContext:
    return TransitionContext(
        context_id="preserve-groove",
        context_version="1",
        goal="preserve_groove",
        desired_energy_direction=None,
        max_tempo_change_percent=8.0,
        minimum_harmonic_fit=None,
        require_phrase_evidence=False,
        allowed_strategies=(
            TransitionStrategy.LONG_BLEND,
            TransitionStrategy.SHORT_BLEND,
            TransitionStrategy.EQ_BLEND,
            TransitionStrategy.CUT,
            TransitionStrategy.HALF_DOUBLE_TIME_SWITCH,
            TransitionStrategy.DELIBERATE_CONTRAST,
        ),
        weights=TransitionWeights(
            tempo_fit=2.0,
            beat_grid_fit=0.0,
            phrase_fit=1.0,
            harmonic_fit=1.5,
            groove_continuity=1.5,
            structural_fit=0.5,
            risk_penalty=0.75,
        ),
    )


def _tempo_match(source: MusicDNARevision, target: MusicDNARevision) -> _TempoMatch | None:
    source_hypotheses = source.rhythm.bpm_hypotheses
    target_hypotheses = target.rhythm.bpm_hypotheses
    if not source_hypotheses or not target_hypotheses:
        return None

    best: _TempoMatch | None = None
    for left in source_hypotheses:
        for right in target_hypotheses:
            denominator = max(left.bpm, right.bpm)
            change_percent = abs(left.bpm - right.bpm) / denominator * 100.0
            fit = max(0.0, 1.0 - change_percent / 10.0)
            candidate = _TempoMatch(
                fit=fit,
                change_percent=change_percent,
                source_relation=left.relation_to_primary,
                target_relation=right.relation_to_primary,
            )
            if best is None or candidate.change_percent < best.change_percent:
                best = candidate
    return best


def _camelot_fit(left: str | None, right: str | None) -> float | None:
    if left is None or right is None:
        return None
    first = _CAMELOT_RE.fullmatch(left.strip().upper())
    second = _CAMELOT_RE.fullmatch(right.strip().upper())
    if first is None or second is None:
        return None
    first_number = int(first.group("number"))
    second_number = int(second.group("number"))
    first_letter = first.group("letter")
    second_letter = second.group("letter")
    if first_number == second_number and first_letter == second_letter:
        return 1.0
    if first_number == second_number and first_letter != second_letter:
        return 0.95
    clockwise = 1 if first_number == 12 else first_number + 1
    counterclockwise = 12 if first_number == 1 else first_number - 1
    if first_letter == second_letter and second_number in {clockwise, counterclockwise}:
        return 0.9
    return 0.2


def _phrase_fit(
    source: MusicDNARevision,
    source_segment: MusicSegmentDNA,
    target: MusicDNARevision,
    target_segment: MusicSegmentDNA,
) -> float | None:
    if (
        source.rhythm.timing_status is FactStatus.UNAVAILABLE
        or target.rhythm.timing_status is FactStatus.UNAVAILABLE
        or not source.rhythm.phrase_boundaries_seconds
        or not target.rhythm.phrase_boundaries_seconds
    ):
        return None
    source_bpm = source.rhythm.dominant_bpm
    target_bpm = target.rhythm.dominant_bpm
    if source_bpm is None or target_bpm is None:
        return None
    source_tolerance = max(0.2, 30.0 / source_bpm)
    target_tolerance = max(0.2, 30.0 / target_bpm)
    source_aligned = any(
        abs(source_segment.end_seconds - boundary) <= source_tolerance
        for boundary in source.rhythm.phrase_boundaries_seconds
    )
    target_aligned = any(
        abs(target_segment.start_seconds - boundary) <= target_tolerance
        for boundary in target.rhythm.phrase_boundaries_seconds
    )
    if source_aligned and target_aligned:
        return 1.0
    if source_aligned or target_aligned:
        return 0.5
    return 0.0


def _groove_fit(source: MusicDNARevision, target: MusicDNARevision) -> float | None:
    left = source.rhythm.percussive_ratio
    right = target.rhythm.percussive_ratio
    if left is None or right is None:
        return None
    return max(0.0, 1.0 - abs(left - right))


def _structural_fit(source: MusicSegmentDNA, target: MusicSegmentDNA) -> float | None:
    if source.structural_label == "unknown" or target.structural_label == "unknown":
        return None
    preferred = {
        ("outro", "intro"),
        ("groove", "groove"),
        ("breakdown", "buildup"),
        ("buildup", "drop"),
    }
    if (source.structural_label, target.structural_label) in preferred:
        return 1.0
    if source.structural_label == target.structural_label:
        return 0.7
    return 0.4


def _transition_confidence(source: MusicDNARevision, target: MusicDNARevision) -> Confidence:
    values = tuple(
        score
        for score in (
            source.rhythm.confidence.score,
            source.tonal.confidence.score,
            target.rhythm.confidence.score,
            target.tonal.confidence.score,
        )
        if score is not None
    )
    return Confidence(
        score=min(values) if values else None,
        calibration_state=(
            CalibrationState.UNCALIBRATED if values else CalibrationState.UNKNOWN
        ),
        evidence_count=len(source.evidence) + len(target.evidence),
    )


def _energy_effect(source: MusicDNARevision, target: MusicDNARevision) -> TransitionEnergyEffect:
    left = source.energy.baseline_energy
    right = target.energy.baseline_energy
    delta = None if left is None or right is None else right - left
    if delta is None:
        direction = EnergyDirection.UNCERTAIN
    elif delta > 0.08:
        direction = EnergyDirection.RISE
    elif delta < -0.08:
        direction = EnergyDirection.FALL
    else:
        direction = EnergyDirection.HOLD
    return TransitionEnergyEffect(
        source_energy_state=left,
        target_energy_state=right,
        delta=delta,
        local_curve_alignment=None,
        direction=direction,
        confidence=Confidence(
            score=None,
            calibration_state=CalibrationState.UNKNOWN,
            evidence_count=len(source.evidence) + len(target.evidence),
        ),
    )


def _risk_vector(
    source: MusicDNARevision,
    target: MusicDNARevision,
    compatibility: TransitionCompatibility,
    confidence: Confidence,
) -> TransitionRisk:
    left_loudness = source.energy.perceived_loudness_db
    right_loudness = target.energy.perceived_loudness_db
    loudness_risk = (
        None
        if left_loudness is None or right_loudness is None
        else min(1.0, abs(left_loudness - right_loudness) / 12.0)
    )
    stability_values = tuple(
        item
        for item in (source.rhythm.beat_stability, target.rhythm.beat_stability)
        if item is not None
    )
    tempo_instability = (
        None if not stability_values else max(0.0, 1.0 - min(stability_values))
    )
    return TransitionRisk(
        bass_collision=None,
        vocal_collision=None,
        spectral_masking=None,
        loudness_discontinuity=loudness_risk,
        harmonic_clash=(
            None if compatibility.harmonic_fit is None else 1.0 - compatibility.harmonic_fit
        ),
        phrase_mismatch=(
            None if compatibility.phrase_fit is None else 1.0 - compatibility.phrase_fit
        ),
        tempo_instability=tempo_instability,
        transient_overload=None,
        uncertainty=1.0 if confidence.score is None else 1.0 - confidence.score,
    )


def _weighted_projection(
    compatibility: TransitionCompatibility,
    risk: TransitionRisk,
    cost: TransitionCost,
    context: TransitionContext,
    confidence: Confidence,
) -> ContextualTransitionProjection:
    blocked: list[str] = []
    if cost.tempo_change_percent is None:
        blocked.append("tempo_evidence_missing")
    elif (
        context.max_tempo_change_percent is not None
        and cost.tempo_change_percent > context.max_tempo_change_percent
    ):
        blocked.append("tempo_change_exceeds_context")
    if context.minimum_harmonic_fit is not None:
        if compatibility.harmonic_fit is None:
            blocked.append("harmonic_evidence_missing")
        elif compatibility.harmonic_fit < context.minimum_harmonic_fit:
            blocked.append("harmonic_fit_below_context")
    if context.require_phrase_evidence and compatibility.phrase_fit is None:
        blocked.append("phrase_evidence_missing")
    if blocked:
        return ContextualTransitionProjection(
            context_id=context.context_id,
            context_version=context.context_version,
            score=None,
            blocked_reasons=tuple(blocked),
            rank_features=(),
            confidence=confidence,
            explanation_codes=tuple(blocked),
        )

    dimension_weights = (
        ("tempo_fit", compatibility.tempo_fit, context.weights.tempo_fit),
        ("beat_grid_fit", compatibility.beat_grid_fit, context.weights.beat_grid_fit),
        ("phrase_fit", compatibility.phrase_fit, context.weights.phrase_fit),
        ("harmonic_fit", compatibility.harmonic_fit, context.weights.harmonic_fit),
        (
            "groove_continuity",
            compatibility.groove_continuity,
            context.weights.groove_continuity,
        ),
        ("structural_fit", compatibility.structural_fit, context.weights.structural_fit),
    )
    available = tuple(
        (name, value, weight)
        for name, value, weight in dimension_weights
        if value is not None and weight > 0.0
    )
    total_weight = sum(weight for _, _, weight in available)
    if total_weight <= 0.0:
        return ContextualTransitionProjection(
            context_id=context.context_id,
            context_version=context.context_version,
            score=None,
            blocked_reasons=("compatibility_evidence_missing",),
            rank_features=(),
            confidence=confidence,
            explanation_codes=("compatibility_evidence_missing",),
        )
    compatibility_score = sum(value * weight for _, value, weight in available) / total_weight
    risk_values = tuple(
        value
        for field_name in risk.__dataclass_fields__
        if field_name != "uncertainty"
        for value in (getattr(risk, field_name),)
        if value is not None
    )
    mean_risk = sum(risk_values) / len(risk_values) if risk_values else risk.uncertainty
    risk_multiplier = max(0.0, 1.0 - min(1.0, mean_risk * context.weights.risk_penalty))
    score = compatibility_score * risk_multiplier
    features = tuple(name for name, _, _ in available)
    return ContextualTransitionProjection(
        context_id=context.context_id,
        context_version=context.context_version,
        score=score,
        blocked_reasons=(),
        rank_features=features,
        confidence=confidence,
        explanation_codes=("context_projection_v1",),
    )


def _strategies(
    compatibility: TransitionCompatibility,
    tempo: _TempoMatch | None,
    energy: TransitionEnergyEffect,
    context: TransitionContext,
) -> tuple[TransitionStrategyCandidate, ...]:
    candidates: list[TransitionStrategyCandidate] = []

    def add(strategy: TransitionStrategy, suitability: float, *codes: str) -> None:
        if strategy not in context.allowed_strategies:
            return
        candidates.append(
            TransitionStrategyCandidate(
                strategy=strategy,
                suitability=suitability,
                required_capabilities=(),
                explanation_codes=tuple(codes),
            )
        )

    add(TransitionStrategy.CUT, 0.6, "cut_requires_minimal_overlap_evidence")
    if compatibility.tempo_fit is not None and compatibility.tempo_fit >= 0.7:
        harmonic = compatibility.harmonic_fit
        if harmonic is None or harmonic >= 0.5:
            add(TransitionStrategy.SHORT_BLEND, 0.72, "tempo_fit_supports_short_blend")
            add(TransitionStrategy.EQ_BLEND, 0.68, "tempo_fit_supports_eq_blend")
    if (
        compatibility.phrase_fit is not None
        and compatibility.phrase_fit >= 0.7
        and compatibility.harmonic_fit is not None
        and compatibility.harmonic_fit >= 0.7
    ):
        add(TransitionStrategy.LONG_BLEND, 0.82, "phrase_and_harmony_support_long_blend")
    if tempo is not None and (
        tempo.source_relation != "primary" or tempo.target_relation != "primary"
    ):
        add(
            TransitionStrategy.HALF_DOUBLE_TIME_SWITCH,
            0.75,
            "tempo_family_relation_supports_switch",
        )
    if energy.direction in {EnergyDirection.RISE, EnergyDirection.FALL}:
        add(
            TransitionStrategy.DELIBERATE_CONTRAST,
            0.62,
            "energy_delta_supports_contrast",
        )
    return tuple(candidates)


def _explanations(
    source: MusicDNARevision,
    target: MusicDNARevision,
    compatibility: TransitionCompatibility,
    risk: TransitionRisk,
    tempo: _TempoMatch | None,
    confidence: Confidence,
) -> tuple[TransitionExplanation, ...]:
    refs = tuple(dict.fromkeys(source.identity.evidence_refs + target.identity.evidence_refs))
    explanations: list[TransitionExplanation] = []

    def add(code: str, severity: str, dimension: str) -> None:
        explanations.append(
            TransitionExplanation(
                code=code,
                severity=severity,
                dimension=dimension,
                evidence_refs=refs,
                confidence=confidence,
            )
        )

    if tempo is None:
        add("tempo_evidence_missing", "warning", "tempo")
    elif tempo.source_relation != "primary" or tempo.target_relation != "primary":
        add("tempo_family_match", "info", "tempo")
    elif tempo.fit >= 0.8:
        add("tempo_fit_strong", "info", "tempo")
    if compatibility.harmonic_fit is None:
        add("harmonic_evidence_missing", "warning", "harmony")
    elif compatibility.harmonic_fit >= 0.9:
        add("harmonic_compatibility_strong", "info", "harmony")
    elif compatibility.harmonic_fit <= 0.3:
        add("harmonic_clash_high", "warning", "harmony")
    if compatibility.phrase_fit is None:
        add("phrase_evidence_unavailable", "info", "phrase")
    elif compatibility.phrase_fit >= 0.7:
        add("phrase_alignment_strong", "info", "phrase")
    if risk.loudness_discontinuity is not None and risk.loudness_discontinuity >= 0.5:
        add("loudness_discontinuity_high", "warning", "loudness")
    return tuple(explanations)


def assess_transition(
    *,
    source: MusicDNARevision,
    source_segment_id: str,
    target: MusicDNARevision,
    target_segment_id: str,
    context: TransitionContext,
    created_at: str,
) -> TransitionAssessment:
    """Build one immutable evidence-backed transition assessment and context projection."""
    if source.identity.track_id == target.identity.track_id:
        raise ValueError("source and target tracks must be different")
    source_segment = source.segment(source_segment_id)
    target_segment = target.segment(target_segment_id)
    tempo = _tempo_match(source, target)
    phrase_fit = _phrase_fit(source, source_segment, target, target_segment)
    compatibility = TransitionCompatibility(
        tempo_fit=None if tempo is None else tempo.fit,
        beat_grid_fit=None,
        phrase_fit=phrase_fit,
        harmonic_fit=_camelot_fit(source.tonal.camelot, target.tonal.camelot),
        groove_continuity=_groove_fit(source, target),
        structural_fit=_structural_fit(source_segment, target_segment),
    )
    confidence = _transition_confidence(source, target)
    risk = _risk_vector(source, target, compatibility, confidence)
    tempo_change = None if tempo is None else tempo.change_percent
    cost = TransitionCost(
        tempo_change_percent=tempo_change,
        time_stretch_cost=(None if tempo_change is None else min(1.0, tempo_change / 8.0)),
        pitch_shift_semitones=None,
        key_shift_cost=None,
        loop_dependency=False,
        stem_dependency=False,
        effect_dependency=False,
        preparation_complexity=None,
    )
    energy = _energy_effect(source, target)
    projection = _weighted_projection(compatibility, risk, cost, context, confidence)
    strategies = _strategies(compatibility, tempo, energy, context)
    if not strategies:
        strategies = (
            TransitionStrategyCandidate(
                strategy=TransitionStrategy.CUT,
                suitability=0.5,
                required_capabilities=(),
                explanation_codes=("fallback_cut",),
            ),
        )
    preferred = max(strategies, key=lambda item: item.suitability).strategy
    identity_material = "|".join(
        (
            source.identity.track_id,
            source_segment.segment_id,
            source.identity.analysis_revision,
            target.identity.track_id,
            target_segment.segment_id,
            target.identity.analysis_revision,
            TRANSITION_ASSESSMENT_VERSION,
            TRANSITION_POLICY_VERSION,
        )
    )
    transition_id = "ta_" + hashlib.sha256(identity_material.encode("utf-8")).hexdigest()[:32]
    identity = TransitionIdentity(
        transition_id=transition_id,
        source_track_id=source.identity.track_id,
        source_segment_id=source_segment.segment_id,
        target_track_id=target.identity.track_id,
        target_segment_id=target_segment.segment_id,
        assessment_version=TRANSITION_ASSESSMENT_VERSION,
        policy_version=TRANSITION_POLICY_VERSION,
        music_dna_revision_refs=(
            source.identity.analysis_revision,
            target.identity.analysis_revision,
        ),
        created_at=created_at,
    )
    window = TransitionWindow(
        source_start_seconds=source_segment.start_seconds,
        source_end_seconds=source_segment.end_seconds,
        target_start_seconds=target_segment.start_seconds,
        target_end_seconds=target_segment.end_seconds,
        source_bar_count=None,
        target_bar_count=None,
        confidence=Confidence(
            score=None,
            calibration_state=CalibrationState.UNKNOWN,
            evidence_count=len(source.evidence) + len(target.evidence),
        ),
    )
    evidence_refs = tuple(
        dict.fromkeys(source.identity.evidence_refs + target.identity.evidence_refs)
    )
    warnings = tuple(
        code
        for code, condition in (
            ("beat_grid_fit_unavailable", compatibility.beat_grid_fit is None),
            ("phrase_fit_unavailable", compatibility.phrase_fit is None),
            ("bass_collision_unavailable", risk.bass_collision is None),
            ("vocal_collision_unavailable", risk.vocal_collision is None),
            ("spectral_masking_unavailable", risk.spectral_masking is None),
        )
        if condition
    )
    return TransitionAssessment(
        identity=identity,
        compatibility_vector=compatibility,
        risk_vector=risk,
        cost_vector=cost,
        energy_effect=energy,
        candidate_strategies=strategies,
        preferred_strategy=preferred,
        usable_window=window,
        contextual_projection=projection,
        confidence=confidence,
        explanations=_explanations(source, target, compatibility, risk, tempo, confidence),
        evidence_refs=evidence_refs,
        warnings=warnings,
    )


__all__ = ["assess_transition", "preserve_groove_context_v1"]
