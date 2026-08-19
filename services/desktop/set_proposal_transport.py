from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace

from core.analysis.provider_contract import CanonicalAnalysisResult
from core.intelligence.music_dna import MusicDNARevision, build_music_dna
from core.intelligence.set_contract import (
    EligibleLibraryScope,
    EnergyControlPoint,
    EnergyTrajectory,
    PlaylistContext,
    PlaylistIntent,
    SequenceState,
    SetGoal,
    SetPhase,
    SetPhaseType,
    SetStep,
)
from core.intelligence.set_optimizer_contract import SetOptimizerPolicy, SetOptimizerResult
from core.intelligence.transition_contract import TransitionAssessment
from data.models.analysis_evidence_record import AnalysisEvidenceRecord
from data.repositories.analysis_evidence_repository import AnalysisEvidenceRepository
from data.repositories.track_repository import TrackRepository
from services.desktop.set_proposal_projection import project_set_optimizer_result
from services.intelligence.phase_context import transition_context_for_phase
from services.intelligence.set_engine import balanced_set_ranking_policy_v1
from services.intelligence.set_path_optimizer import optimize_set_lookahead
from services.intelligence.transition_engine import assess_transition, preserve_groove_context_v1

MIN_SET_PROPOSAL_TRACKS = 3
MAX_SET_PROPOSAL_TRACKS = 24
MIN_SET_PROPOSAL_TARGET_TRACKS = 3
MAX_SET_PROPOSAL_TARGET_TRACKS = 8
MAX_SET_PROPOSAL_TRACK_ID_CHARS = 256
SET_PROPOSAL_POLICY_VERSION = "desktop-set-proposal-preview-r1"
SET_PROPOSAL_PHASE_ID = "phase:preview-groove"
SET_PROPOSAL_GENERATED_AT = "desktop-set-proposal-r1"

_CANONICAL_WARNING_CODES = {
    "bounded search intentionally pruned lower-priority frontier states": "bounded_search_pruned_frontier",
    "one or more persisted outgoing edges lacked target duration evidence": "candidate_duration_evidence_missing",
    (
        "future feasibility is not a hard beam prune in optimizer v1 because its current "
        "contract uses one fixed TransitionContext across the evaluated horizon"
    ): "future_feasibility_not_hard_prune_v1",
}


class DesktopSetProposalTransportError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _TransientTransitionRepository:
    """Request-local adjacency only; never persists TransitionAssessment state."""

    def __init__(self, assessments: Sequence[TransitionAssessment]) -> None:
        self._assessments = tuple(assessments)

    def list_outgoing(
        self,
        *,
        source_track_id: str,
        source_segment_id: str,
        context_id: str | None = None,
        context_version: str | None = None,
        assessment_version: str | None = None,
        policy_version: str | None = None,
    ) -> tuple[TransitionAssessment, ...]:
        if (context_id is None) != (context_version is None):
            raise ValueError("context_id and context_version must be supplied together")
        matches = [
            item
            for item in self._assessments
            if item.identity.source_track_id == source_track_id
            and item.identity.source_segment_id == source_segment_id
            and (context_id is None or item.contextual_projection.context_id == context_id)
            and (
                context_version is None
                or item.contextual_projection.context_version == context_version
            )
            and (
                assessment_version is None
                or item.identity.assessment_version == assessment_version
            )
            and (policy_version is None or item.identity.policy_version == policy_version)
        ]
        return tuple(
            sorted(
                matches,
                key=lambda item: (
                    item.identity.transition_id,
                    item.identity.target_track_id,
                    item.identity.target_segment_id,
                ),
            )
        )


class DesktopSetProposalTransport:
    """Evidence-only bridge from persisted analysis truth to Bundle 56 projection."""

    def __init__(
        self,
        *,
        evidence_repository: AnalysisEvidenceRepository | None = None,
        track_repository: TrackRepository | None = None,
    ) -> None:
        self._evidence = evidence_repository or AnalysisEvidenceRepository()
        self._tracks = track_repository or TrackRepository()

    def generate(
        self,
        *,
        track_ids: Sequence[str],
        seed_track_id: str,
        target_track_count: int,
    ) -> dict[str, object]:
        scope = self._validated_track_ids(track_ids)
        seed = self._validated_track_id(seed_track_id)
        if seed not in scope:
            raise DesktopSetProposalTransportError(
                "invalid_set_proposal_request",
                "The seed track must be inside the selected proposal scope.",
            )
        target = self._validated_target_track_count(target_track_count, len(scope))

        revisions: dict[str, MusicDNARevision] = {}
        durations: dict[str, float] = {}
        labels: dict[str, str] = {}
        for track_id in scope:
            revision, duration, label = self._revision_for_track(track_id)
            revisions[track_id] = revision
            durations[track_id] = duration
            labels[track_id] = label

        request_fingerprint = self._request_fingerprint(scope, seed, target)
        phase = SetPhase(
            phase_id=SET_PROPOSAL_PHASE_ID,
            phase_type=SetPhaseType.GROOVE,
            ordinal=0,
            target_fraction_start=0.0,
            target_fraction_end=1.0,
            explanation_label="Read-only desktop proposal preview",
        )
        seed_energy = revisions[seed].energy.baseline_energy
        if seed_energy is None:
            raise DesktopSetProposalTransportError(
                "set_proposal_analysis_incomplete",
                "The seed track is missing required energy evidence.",
            )
        trajectory = EnergyTrajectory(
            trajectory_id=f"trajectory:{request_fingerprint[:24]}",
            trajectory_version=SET_PROPOSAL_POLICY_VERSION,
            control_points=(
                EnergyControlPoint(
                    normalized_set_position=0.0,
                    target_energy=seed_energy,
                    tolerance=0.35,
                    phase_id=SET_PROPOSAL_PHASE_ID,
                ),
                EnergyControlPoint(
                    normalized_set_position=1.0,
                    target_energy=seed_energy,
                    tolerance=0.35,
                    phase_id=SET_PROPOSAL_PHASE_ID,
                ),
            ),
        )
        intent = PlaylistIntent(
            intent_id=f"intent:{request_fingerprint[:24]}",
            intent_version=SET_PROPOSAL_POLICY_VERSION,
            goal=SetGoal.CLUB_FLOW,
            eligible_library_scope=EligibleLibraryScope(
                scope_revision=f"scope:{request_fingerprint[:24]}",
                explicit_track_ids=scope,
            ),
            phase_plan=(phase,),
            energy_trajectory=trajectory,
            target_track_count=target,
            allow_track_repeats=False,
            reject_critical_warnings=True,
        )
        seed_revision = revisions[seed]
        seed_segment = seed_revision.segments[0]
        root_step = SetStep(
            order_index=0,
            track_id=seed,
            segment_id=seed_segment.segment_id,
            phase_id=SET_PROPOSAL_PHASE_ID,
            evidence_refs=seed_revision.identity.evidence_refs,
        )
        root_state = SequenceState(
            state_id=f"state:{request_fingerprint[:24]}",
            state_version=SET_PROPOSAL_POLICY_VERSION,
            selected_steps=(root_step,),
            current_track_id=seed,
            current_segment_id=seed_segment.segment_id,
            used_track_ids=(seed,),
            cumulative_duration_seconds=durations[seed],
            current_energy_state=seed_energy,
            evidence_refs=seed_revision.identity.evidence_refs,
        )
        root_context = PlaylistContext(
            context_id=f"context:{request_fingerprint[:24]}",
            context_version=SET_PROPOSAL_POLICY_VERSION,
            current_phase_id=SET_PROPOSAL_PHASE_ID,
            current_position_index=0,
            elapsed_duration_seconds=durations[seed],
            phase_progress=min(1.0, 1.0 / target),
            current_track_id=seed,
            current_segment_id=seed_segment.segment_id,
            current_energy_state=seed_energy,
            remaining_track_count=max(0, target - 1),
            context_evidence_refs=seed_revision.identity.evidence_refs,
        )
        base_transition_context = preserve_groove_context_v1()
        phase_transition_context = transition_context_for_phase(
            phase=phase,
            base_context=base_transition_context,
        )

        assessments: list[TransitionAssessment] = []
        for source_id in scope:
            source = revisions[source_id]
            source_segment = source.segments[0]
            for target_id in scope:
                if target_id == source_id:
                    continue
                target_revision = revisions[target_id]
                target_segment = target_revision.segments[0]
                assessments.append(
                    assess_transition(
                        source=source,
                        source_segment_id=source_segment.segment_id,
                        target=target_revision,
                        target_segment_id=target_segment.segment_id,
                        context=phase_transition_context,
                        created_at=SET_PROPOSAL_GENERATED_AT,
                    )
                )

        repository = _TransientTransitionRepository(assessments)
        optimizer_policy = SetOptimizerPolicy(
            beam_width=8,
            max_depth=target - 1,
            per_state_candidate_limit=min(16, len(scope) - 1),
            max_expanded_candidates=2_048,
            alternative_limit=3,
        )
        result = optimize_set_lookahead(
            repository=repository,  # type: ignore[arg-type]
            intent=intent,
            root_context=root_context,
            root_state=root_state,
            base_transition_context=base_transition_context,
            ranking_policy=balanced_set_ranking_policy_v1(),
            optimizer_policy=optimizer_policy,
            target_duration_seconds_by_track=durations,
            generated_at=SET_PROPOSAL_GENERATED_AT,
            style_tags_by_track=None,
            critical_warnings_by_track={track_id: () for track_id in scope},
        )
        safe_result = self._renderer_safe_result(result)
        try:
            return project_set_optimizer_result(
                result=safe_result,
                display_name_by_track_id=labels,
            )
        except ValueError as exc:
            raise DesktopSetProposalTransportError(
                "set_proposal_projection_failed",
                "The set proposal could not be projected safely.",
            ) from exc

    def _revision_for_track(
        self,
        track_id: str,
    ) -> tuple[MusicDNARevision, float, str]:
        attempt = self._evidence.latest_evidence_for_track(track_id)
        if attempt is None:
            raise DesktopSetProposalTransportError(
                "set_proposal_analysis_missing",
                "Analysis evidence is missing for a selected track.",
            )
        if attempt.status != "succeeded":
            raise DesktopSetProposalTransportError(
                "set_proposal_analysis_failed",
                "The latest analysis attempt failed for a selected track.",
            )
        success = self._evidence.latest_success_for_track(track_id)
        if success is None or success.evidence_id != attempt.evidence_id:
            raise DesktopSetProposalTransportError(
                "set_proposal_analysis_failed",
                "A selected track has no current successful analysis evidence.",
            )
        if (
            success.provider_version is None
            or success.algorithm_version is None
            or success.duration_seconds is None
            or success.duration_seconds <= 0.0
            or success.bpm is None
            or success.energy is None
        ):
            raise DesktopSetProposalTransportError(
                "set_proposal_analysis_incomplete",
                "A selected track is missing required analysis evidence.",
            )

        correction = self._evidence.latest_active_correction(track_id, success.evidence_id)
        correction_values: Mapping[str, object] = {}
        correction_id: str | None = None
        if correction is not None:
            try:
                decoded = json.loads(correction.payload_json)
            except json.JSONDecodeError as exc:
                raise DesktopSetProposalTransportError(
                    "set_proposal_analysis_incomplete",
                    "A selected track has invalid correction evidence.",
                ) from exc
            if not isinstance(decoded, dict) or set(decoded) - {
                "bpm",
                "key_tonic",
                "key_scale",
                "camelot",
                "energy",
            }:
                raise DesktopSetProposalTransportError(
                    "set_proposal_analysis_incomplete",
                    "A selected track has invalid correction evidence.",
                )
            correction_values = decoded
            correction_id = correction.correction_id

        canonical = self._canonical_result(success, correction_values)
        analysis_revision = success.evidence_id
        if correction_id is not None:
            analysis_revision = f"{analysis_revision}+{correction_id}"
        try:
            revision = build_music_dna(
                track_id=track_id,
                content_identity=track_id,
                analysis_revision=analysis_revision,
                evidence_id=success.evidence_id,
                input_identity=track_id,
                canonical=canonical,
                rhythmic_structure=None,
                benchmark_status="desktop-preview",
            )
        except ValueError as exc:
            raise DesktopSetProposalTransportError(
                "set_proposal_analysis_incomplete",
                "A selected track cannot form a valid Music DNA revision.",
            ) from exc

        track = self._tracks.get_by_id(track_id)
        if track is None:
            raise DesktopSetProposalTransportError(
                "set_proposal_track_unavailable",
                "A selected track is not available in the local library.",
            )
        title = track.title.strip() if isinstance(track.title, str) and track.title.strip() else track_id
        artist = (
            track.artist.strip()
            if isinstance(track.artist, str) and track.artist.strip()
            else None
        )
        label = f"{artist} — {title}" if artist is not None else title
        return revision, float(success.duration_seconds), label

    @staticmethod
    def _canonical_result(
        evidence: AnalysisEvidenceRecord,
        correction: Mapping[str, object],
    ) -> CanonicalAnalysisResult:
        def corrected(name: str, provider_value: object) -> object:
            return correction[name] if name in correction else provider_value

        bpm = corrected("bpm", evidence.bpm)
        energy = corrected("energy", evidence.energy)
        tonic = corrected("key_tonic", evidence.key_tonic)
        scale = corrected("key_scale", evidence.key_scale)
        camelot = corrected("camelot", evidence.camelot)
        key = None
        if isinstance(camelot, str):
            key = camelot
        elif isinstance(tonic, str):
            key = tonic if not isinstance(scale, str) else f"{tonic} {scale}"
        return CanonicalAnalysisResult(
            path=evidence.track_id,
            provider=evidence.provider,
            bpm=float(bpm) if isinstance(bpm, (int, float)) and not isinstance(bpm, bool) else None,
            bpm_confidence=evidence.bpm_confidence,
            key=key,
            key_confidence=evidence.key_confidence,
            energy=(
                float(energy)
                if isinstance(energy, (int, float)) and not isinstance(energy, bool)
                else None
            ),
            loudness_db=evidence.loudness_db,
            duration_seconds=evidence.duration_seconds,
            genre_hint=evidence.genre_hint,
            analysis_status="ok",
            analysis_version=evidence.analysis_version,
            key_tonic=tonic if isinstance(tonic, str) else None,
            key_scale=scale if isinstance(scale, str) else None,
            camelot=camelot if isinstance(camelot, str) else None,
            beat_stability=evidence.beat_stability,
            harmonic_ratio=evidence.harmonic_ratio,
            percussive_ratio=evidence.percussive_ratio,
            provider_version=evidence.provider_version,
            algorithm_version=evidence.algorithm_version,
            warnings=evidence.warnings,
        )

    @staticmethod
    def _renderer_safe_result(result: SetOptimizerResult) -> SetOptimizerResult:
        normalized: list[str] = []
        for warning in result.warnings:
            code = _CANONICAL_WARNING_CODES.get(warning)
            if code is None:
                raise DesktopSetProposalTransportError(
                    "set_proposal_projection_failed",
                    "The optimizer returned an unrecognized renderer warning.",
                )
            if code not in normalized:
                normalized.append(code)
        return replace(result, warnings=tuple(normalized))

    @classmethod
    def _validated_track_ids(cls, values: Sequence[str]) -> tuple[str, ...]:
        if isinstance(values, (str, bytes)):
            raise DesktopSetProposalTransportError(
                "invalid_set_proposal_request",
                "Proposal track_ids must be a bounded list.",
            )
        if not MIN_SET_PROPOSAL_TRACKS <= len(values) <= MAX_SET_PROPOSAL_TRACKS:
            raise DesktopSetProposalTransportError(
                "invalid_set_proposal_request",
                "Proposal track_ids must contain between 3 and 24 tracks.",
            )
        normalized = tuple(cls._validated_track_id(value) for value in values)
        if len(set(normalized)) != len(normalized):
            raise DesktopSetProposalTransportError(
                "invalid_set_proposal_request",
                "Proposal track_ids must be unique.",
            )
        return tuple(sorted(normalized))

    @staticmethod
    def _validated_track_id(value: object) -> str:
        if not isinstance(value, str):
            raise DesktopSetProposalTransportError(
                "invalid_set_proposal_request",
                "The set proposal track identifier is invalid.",
            )
        normalized = value.strip()
        if (
            not normalized
            or len(normalized) > MAX_SET_PROPOSAL_TRACK_ID_CHARS
            or normalized != value
            or "/" in normalized
            or "\\" in normalized
            or any(ord(character) < 32 or ord(character) == 127 for character in normalized)
        ):
            raise DesktopSetProposalTransportError(
                "invalid_set_proposal_request",
                "The set proposal track identifier is invalid.",
            )
        return normalized

    @staticmethod
    def _validated_target_track_count(value: object, scope_size: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise DesktopSetProposalTransportError(
                "invalid_set_proposal_request",
                "The set proposal target track count is invalid.",
            )
        if (
            value < MIN_SET_PROPOSAL_TARGET_TRACKS
            or value > MAX_SET_PROPOSAL_TARGET_TRACKS
            or value > scope_size
        ):
            raise DesktopSetProposalTransportError(
                "invalid_set_proposal_request",
                "The set proposal target track count is outside the bounded scope.",
            )
        return value

    @staticmethod
    def _request_fingerprint(
        scope: tuple[str, ...],
        seed_track_id: str,
        target_track_count: int,
    ) -> str:
        material = "|".join((*scope, seed_track_id, str(target_track_count), SET_PROPOSAL_POLICY_VERSION))
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


__all__ = [
    "DesktopSetProposalTransport",
    "DesktopSetProposalTransportError",
    "MAX_SET_PROPOSAL_TRACKS",
    "MIN_SET_PROPOSAL_TRACKS",
    "SET_PROPOSAL_POLICY_VERSION",
]
