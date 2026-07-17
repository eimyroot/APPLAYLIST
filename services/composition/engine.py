from __future__ import annotations

from collections.abc import Iterable

from services.composition.camelot import normalize_camelot
from services.composition.models import (
    CompositionDecision,
    CompositionFailureReason,
    CompositionMode,
    CompositionRequest,
    CompositionResult,
    CompositionStatus,
    CompositionSummary,
    CompositionTrack,
    EnergyStage,
    TransitionReason,
    TransitionScore,
)
from services.composition.scoring import score_transition, target_energy


_MODE_STAGE_PLANS: dict[CompositionMode, tuple[EnergyStage, ...]] = {
    CompositionMode.WARMUP: (
        EnergyStage.INTRO,
        EnergyStage.WARMUP,
        EnergyStage.GROOVE,
        EnergyStage.GROOVE,
        EnergyStage.AFTERGLOW,
        EnergyStage.CLOSING,
    ),
    CompositionMode.CLUB: (
        EnergyStage.INTRO,
        EnergyStage.WARMUP,
        EnergyStage.GROOVE,
        EnergyStage.LIFT,
        EnergyStage.PEAK,
        EnergyStage.AFTERGLOW,
        EnergyStage.CLOSING,
    ),
    CompositionMode.FESTIVAL: (
        EnergyStage.INTRO,
        EnergyStage.GROOVE,
        EnergyStage.LIFT,
        EnergyStage.PEAK,
        EnergyStage.PEAK,
        EnergyStage.AFTERGLOW,
        EnergyStage.CLOSING,
    ),
    CompositionMode.AFTERHOURS: (
        EnergyStage.INTRO,
        EnergyStage.WARMUP,
        EnergyStage.GROOVE,
        EnergyStage.AFTERGLOW,
        EnergyStage.CLOSING,
    ),
    CompositionMode.CUSTOM: (
        EnergyStage.INTRO,
        EnergyStage.GROOVE,
        EnergyStage.PEAK,
        EnergyStage.CLOSING,
    ),
}


class DeterministicCompositionEngine:
    """Pure composition engine with no I/O, repositories, network or global state."""

    def compose(self, request: CompositionRequest) -> CompositionResult:
        candidates, duplicate_count = self._eligible_candidates(request)
        warnings: list[str] = []
        if duplicate_count:
            warnings.append(f"Removed {duplicate_count} duplicate track_id candidate(s).")

        if not candidates:
            return CompositionResult(
                status=CompositionStatus.FAILED,
                failure_reason=CompositionFailureReason.NO_CANDIDATES,
                tracks=(),
                decisions=(),
                summary=self._summarize(()),
                warnings=tuple(warnings),
            )

        target_count = min(request.target_track_count, len(candidates))
        if target_count < request.target_track_count:
            warnings.append(
                "Requested track count exceeds the number of eligible unique candidates."
            )

        stages = self._stage_plan(request, target_count)
        opening = self._pick_opening_track(candidates, request, stages[0])
        opening_score = TransitionScore(
            total=0.0,
            eligible=True,
            bpm_delta=0.0,
            harmonic_compatible=True,
            energy_distance=abs(opening.energy - target_energy(request, stages[0])),
            artist_spacing_ok=True,
            label_spacing_ok=True,
            source_rotation_ok=True,
            reasons=(
                TransitionReason(
                    code="opening_track",
                    value=1.0,
                    weight=0.0,
                    contribution=0.0,
                    passed=True,
                ),
            ),
        )

        playlist = [opening]
        decisions = [
            CompositionDecision(
                order_index=0,
                track_id=opening.track_id,
                stage=stages[0],
                score=opening_score,
            )
        ]
        used_ids = {opening.track_id}
        stalled = False

        while len(playlist) < target_count:
            stage = stages[len(playlist)]
            current = playlist[-1]
            scored = [
                (
                    candidate,
                    score_transition(
                        current=current,
                        candidate=candidate,
                        playlist=playlist,
                        stage=stage,
                        request=request,
                    ),
                )
                for candidate in candidates
                if candidate.track_id not in used_ids
            ]
            eligible = [item for item in scored if item[1].eligible]
            if not eligible:
                stalled = True
                warnings.append(
                    "Composition stopped because no remaining candidate passed the BPM hard gate."
                )
                break

            selected, selected_score = sorted(
                eligible,
                key=lambda item: (
                    -item[1].total,
                    item[1].energy_distance,
                    item[1].bpm_delta,
                    item[0].track_id,
                    item[0].path,
                ),
            )[0]
            playlist.append(selected)
            used_ids.add(selected.track_id)
            decisions.append(
                CompositionDecision(
                    order_index=len(playlist) - 1,
                    track_id=selected.track_id,
                    stage=stage,
                    score=selected_score,
                )
            )

        if len(playlist) == request.target_track_count:
            status = CompositionStatus.SUCCESS
            failure_reason = None
        else:
            status = CompositionStatus.PARTIAL
            failure_reason = (
                CompositionFailureReason.COMPOSITION_STALLED
                if stalled
                else CompositionFailureReason.NO_CANDIDATES
            )

        return CompositionResult(
            status=status,
            failure_reason=failure_reason,
            tracks=tuple(playlist),
            decisions=tuple(decisions),
            summary=self._summarize(playlist),
            warnings=tuple(warnings),
        )

    @staticmethod
    def _eligible_candidates(
        request: CompositionRequest,
    ) -> tuple[list[CompositionTrack], int]:
        genre_target = request.genre.strip().casefold() if request.genre else None
        filtered = [
            track
            for track in request.tracks
            if request.bpm_min <= track.bpm <= request.bpm_max
            and (
                genre_target is None
                or genre_target in track.genre.strip().casefold()
            )
        ]
        ordered = sorted(
            filtered,
            key=lambda track: (
                track.track_id,
                track.path,
                track.bpm,
                track.energy,
                track.camelot,
            ),
        )
        unique: dict[str, CompositionTrack] = {}
        for track in ordered:
            unique.setdefault(track.track_id, track)
        return list(unique.values()), len(ordered) - len(unique)

    @staticmethod
    def _pick_opening_track(
        candidates: list[CompositionTrack],
        request: CompositionRequest,
        stage: EnergyStage,
    ) -> CompositionTrack:
        pool = candidates
        requested_key = normalize_camelot(request.start_key)
        if requested_key is not None:
            matching = [
                track
                for track in candidates
                if normalize_camelot(track.camelot) == requested_key
            ]
            if matching:
                pool = matching
        target = target_energy(request, stage)
        return sorted(
            pool,
            key=lambda track: (
                abs(track.energy - target),
                track.bpm,
                track.track_id,
                track.path,
            ),
        )[0]

    @staticmethod
    def _stage_plan(
        request: CompositionRequest,
        target_count: int,
    ) -> tuple[EnergyStage, ...]:
        base = (
            tuple(point.stage for point in request.energy_curve)
            if request.energy_curve
            else _MODE_STAGE_PLANS[request.mode]
        )
        if not base:
            base = (EnergyStage.GROOVE,)
        return tuple(
            base[min((index * len(base)) // target_count, len(base) - 1)]
            for index in range(target_count)
        )

    @staticmethod
    def _summarize(tracks: Iterable[CompositionTrack]) -> CompositionSummary:
        materialized = tuple(tracks)
        if not materialized:
            return CompositionSummary(
                track_count=0,
                total_duration_seconds=0,
                average_bpm=0.0,
                minimum_bpm=0.0,
                maximum_bpm=0.0,
                average_energy=0.0,
            )
        bpms = [track.bpm for track in materialized]
        energies = [track.energy for track in materialized]
        return CompositionSummary(
            track_count=len(materialized),
            total_duration_seconds=sum(track.duration_seconds for track in materialized),
            average_bpm=sum(bpms) / len(bpms),
            minimum_bpm=min(bpms),
            maximum_bpm=max(bpms),
            average_energy=sum(energies) / len(energies),
        )
