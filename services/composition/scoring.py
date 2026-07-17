from __future__ import annotations

from services.composition.camelot import camelot_compatible
from services.composition.models import (
    CompositionRequest,
    CompositionTrack,
    EnergyStage,
    TransitionReason,
    TransitionScore,
)


DEFAULT_ENERGY_TARGETS: dict[EnergyStage, float] = {
    EnergyStage.INTRO: 0.25,
    EnergyStage.WARMUP: 0.35,
    EnergyStage.GROOVE: 0.50,
    EnergyStage.LIFT: 0.68,
    EnergyStage.PEAK: 0.86,
    EnergyStage.AFTERGLOW: 0.60,
    EnergyStage.CLOSING: 0.42,
}


def target_energy(request: CompositionRequest, stage: EnergyStage) -> float:
    for point in request.energy_curve:
        if point.stage == stage:
            return point.target
    return DEFAULT_ENERGY_TARGETS[stage]


def score_transition(
    *,
    current: CompositionTrack,
    candidate: CompositionTrack,
    playlist: list[CompositionTrack],
    stage: EnergyStage,
    request: CompositionRequest,
) -> TransitionScore:
    constraints = request.constraints
    bpm_delta = abs(candidate.bpm - current.bpm)
    bpm_limit = (
        constraints.bpm_jump_max_peak
        if stage == EnergyStage.PEAK
        else constraints.bpm_jump_max
    )
    energy_distance = abs(candidate.energy - target_energy(request, stage))

    if bpm_delta > bpm_limit:
        return TransitionScore(
            total=-1_000_000.0,
            eligible=False,
            bpm_delta=bpm_delta,
            harmonic_compatible=False,
            energy_distance=energy_distance,
            artist_spacing_ok=False,
            label_spacing_ok=False,
            source_rotation_ok=False,
            reasons=(
                TransitionReason(
                    code="bpm_hard_gate",
                    value=bpm_delta,
                    weight=1.0,
                    contribution=-1_000_000.0,
                    passed=False,
                ),
            ),
        )

    reasons: list[TransitionReason] = []
    bpm_value = max(0.0, 1.0 - (bpm_delta / bpm_limit))
    reasons.append(_weighted_reason("bpm_flow", bpm_value, 2.0))

    harmonic_ok = camelot_compatible(
        current.camelot,
        candidate.camelot,
        allow_same=constraints.allow_same_key,
        allow_adjacent=constraints.allow_adjacent_camelot,
        allow_relative=constraints.allow_relative_key,
    )
    reasons.append(
        TransitionReason(
            code="harmonic_compatibility",
            value=1.0 if harmonic_ok else 0.0,
            weight=2.0,
            contribution=2.0 if harmonic_ok else -1.5,
            passed=harmonic_ok,
        )
    )

    energy_value = max(0.0, 1.0 - energy_distance)
    reasons.append(_weighted_reason("energy_target", energy_value, 2.0))

    genre_ok = (
        request.genre is None
        or request.genre.strip().casefold()
        in candidate.genre.strip().casefold()
    )
    reasons.append(_binary_reason("genre_match", genre_ok, 0.5))

    artist_ok = _spacing_ok(
        candidate.artist,
        playlist,
        attribute="artist",
        minimum_gap=constraints.same_artist_min_gap,
    )
    reasons.append(_binary_reason("artist_spacing", artist_ok, 0.75))

    label_ok = _spacing_ok(
        candidate.label,
        playlist,
        attribute="label",
        minimum_gap=constraints.same_label_min_gap,
    )
    reasons.append(_binary_reason("label_spacing", label_ok, 0.5))

    source_ok = _source_rotation_ok(
        candidate.source_folder,
        playlist,
        constraints.same_source_folder_max_consecutive,
    )
    reasons.append(_binary_reason("source_rotation", source_ok, 0.5))

    return TransitionScore(
        total=sum(reason.contribution for reason in reasons),
        eligible=True,
        bpm_delta=bpm_delta,
        harmonic_compatible=harmonic_ok,
        energy_distance=energy_distance,
        artist_spacing_ok=artist_ok,
        label_spacing_ok=label_ok,
        source_rotation_ok=source_ok,
        reasons=tuple(reasons),
    )


def _weighted_reason(code: str, value: float, weight: float) -> TransitionReason:
    return TransitionReason(
        code=code,
        value=value,
        weight=weight,
        contribution=value * weight,
        passed=True,
    )


def _binary_reason(code: str, passed: bool, weight: float) -> TransitionReason:
    return TransitionReason(
        code=code,
        value=1.0 if passed else 0.0,
        weight=weight,
        contribution=weight if passed else -weight,
        passed=passed,
    )


def _spacing_ok(
    value: str | None,
    playlist: list[CompositionTrack],
    *,
    attribute: str,
    minimum_gap: int,
) -> bool:
    if not value or minimum_gap <= 0:
        return True
    normalized = value.strip().casefold()
    recent = playlist[-minimum_gap:]
    return all(
        not existing or existing.strip().casefold() != normalized
        for existing in (getattr(track, attribute) for track in recent)
    )


def _source_rotation_ok(
    source_folder: str | None,
    playlist: list[CompositionTrack],
    maximum_consecutive: int,
) -> bool:
    if not source_folder:
        return True
    normalized = source_folder.strip().casefold()
    consecutive = 0
    for track in reversed(playlist):
        existing = track.source_folder
        if not existing or existing.strip().casefold() != normalized:
            break
        consecutive += 1
    return consecutive < maximum_consecutive
