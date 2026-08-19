from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from core.intelligence.set_contract import (
    EligibleLibraryScope,
    EnergyControlPoint,
    EnergyTrajectory,
    LockedPosition,
    PlaylistContext,
    PlaylistIntent,
    SequenceState,
    SetGoal,
    SetPhase,
    SetPhaseType,
    SetStep,
)
from core.intelligence.set_optimizer_contract import SetOptimizerPolicy
from core.intelligence.transition_contract import TransitionAssessment
from services.desktop.set_proposal_projection import project_set_optimizer_result
from services.desktop.set_proposal_transport import (
    DesktopSetProposalTransport,
    DesktopSetProposalTransportError,
)
from services.intelligence.phase_context import transition_context_for_phase
from services.intelligence.set_engine import balanced_set_ranking_policy_v1
from services.intelligence.set_path_optimizer import optimize_set_lookahead
from services.intelligence.transition_engine import assess_transition, preserve_groove_context_v1

PLAYLIST_REGENERATION_SCHEMA = "applaylist-desktop-playlist-regeneration-r1"
PLAYLIST_REGENERATION_POLICY_VERSION = "desktop-playlist-regeneration-r1"
PLAYLIST_REGENERATION_PHASE_ID = "phase:regeneration-groove"
PLAYLIST_REGENERATION_GENERATED_AT = "desktop-playlist-regeneration-r1"


class DesktopPlaylistRegenerationTransportError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _TransientTransitionRepository:
    """Request-local adjacency used only by bounded regeneration preview."""

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


class DesktopPlaylistRegenerationTransport(DesktopSetProposalTransport):
    """Deterministic bounded regeneration around immutable playlist locks.

    R1 deliberately requires position zero to be locked so the existing seeded Set
    Intelligence optimizer remains the only path-search authority. Transition
    assessments are rebuilt request-locally from persisted analysis evidence exactly
    like the desktop set proposal preview and are never persisted by this transport.
    """

    def generate(
        self,
        *,
        parent_revision: dict[str, object],
        candidate_track_ids: Sequence[str],
    ) -> dict[str, object]:
        parent_id, playlist_id, parent_fingerprint, parent_items = self._parent(parent_revision)
        locked = tuple(
            (index, str(item["track_id"]))
            for index, item in enumerate(parent_items)
            if bool(item["locked"])
        )
        if not locked or locked[0][0] != 0:
            raise DesktopPlaylistRegenerationTransportError(
                "playlist_regeneration_anchor_required",
                "Regeneration R1 requires the first playlist position to be locked.",
            )

        try:
            scope = self._validated_track_ids(candidate_track_ids)
            target = self._validated_target_track_count(len(parent_items), len(scope))
        except DesktopSetProposalTransportError as exc:
            raise DesktopPlaylistRegenerationTransportError(
                "invalid_playlist_regeneration_request",
                "The regeneration candidate pool is invalid.",
            ) from exc

        locked_ids = tuple(track_id for _, track_id in locked)
        if any(track_id not in scope for track_id in locked_ids):
            raise DesktopPlaylistRegenerationTransportError(
                "playlist_regeneration_locked_track_missing",
                "The candidate pool must include every locked playlist track.",
            )

        seed = str(parent_items[0]["track_id"])
        revisions = {}
        durations: dict[str, float] = {}
        labels: dict[str, str] = {}
        for track_id in scope:
            try:
                revision, duration, label = self._revision_for_track(track_id)
            except DesktopSetProposalTransportError as exc:
                raise DesktopPlaylistRegenerationTransportError(
                    "playlist_regeneration_evidence_unavailable",
                    "A candidate track cannot be regenerated from current analysis evidence.",
                ) from exc
            revisions[track_id] = revision
            durations[track_id] = duration
            labels[track_id] = label

        request_fingerprint = self._request_fingerprint_r1(
            parent_revision_id=parent_id,
            parent_content_fingerprint=parent_fingerprint,
            scope=scope,
            locked=locked,
        )
        phase = SetPhase(
            phase_id=PLAYLIST_REGENERATION_PHASE_ID,
            phase_type=SetPhaseType.GROOVE,
            ordinal=0,
            target_fraction_start=0.0,
            target_fraction_end=1.0,
            explanation_label="Governed regeneration around immutable locks",
        )
        seed_revision = revisions[seed]
        seed_energy = seed_revision.energy.baseline_energy
        if seed_energy is None:
            raise DesktopPlaylistRegenerationTransportError(
                "playlist_regeneration_evidence_unavailable",
                "The locked seed track is missing required energy evidence.",
            )
        trajectory = EnergyTrajectory(
            trajectory_id=f"trajectory:{request_fingerprint[:24]}",
            trajectory_version=PLAYLIST_REGENERATION_POLICY_VERSION,
            control_points=(
                EnergyControlPoint(
                    normalized_set_position=0.0,
                    target_energy=seed_energy,
                    tolerance=0.35,
                    phase_id=PLAYLIST_REGENERATION_PHASE_ID,
                ),
                EnergyControlPoint(
                    normalized_set_position=1.0,
                    target_energy=seed_energy,
                    tolerance=0.35,
                    phase_id=PLAYLIST_REGENERATION_PHASE_ID,
                ),
            ),
        )
        lock_contract = tuple(
            LockedPosition(
                track_id=track_id,
                lock_version=f"revision:{parent_id}",
                position_index=index,
            )
            for index, track_id in locked
        )
        intent = PlaylistIntent(
            intent_id=f"intent:{request_fingerprint[:24]}",
            intent_version=PLAYLIST_REGENERATION_POLICY_VERSION,
            goal=SetGoal.CLUB_FLOW,
            eligible_library_scope=EligibleLibraryScope(
                scope_revision=f"scope:{request_fingerprint[:24]}",
                explicit_track_ids=scope,
            ),
            phase_plan=(phase,),
            energy_trajectory=trajectory,
            target_track_count=target,
            required_track_ids=locked_ids,
            locked_positions=lock_contract,
            allow_track_repeats=False,
            reject_critical_warnings=True,
        )

        seed_segment = seed_revision.segments[0]
        root_step = SetStep(
            order_index=0,
            track_id=seed,
            segment_id=seed_segment.segment_id,
            phase_id=PLAYLIST_REGENERATION_PHASE_ID,
            evidence_refs=seed_revision.identity.evidence_refs,
        )
        root_state = SequenceState(
            state_id=f"state:{request_fingerprint[:24]}",
            state_version=PLAYLIST_REGENERATION_POLICY_VERSION,
            selected_steps=(root_step,),
            current_track_id=seed,
            current_segment_id=seed_segment.segment_id,
            used_track_ids=(seed,),
            cumulative_duration_seconds=durations[seed],
            current_energy_state=seed_energy,
            satisfied_required_track_ids=(seed,),
            remaining_required_track_ids=tuple(item for item in locked_ids if item != seed),
            evidence_refs=seed_revision.identity.evidence_refs,
        )
        root_context = PlaylistContext(
            context_id=f"context:{request_fingerprint[:24]}",
            context_version=PLAYLIST_REGENERATION_POLICY_VERSION,
            current_phase_id=PLAYLIST_REGENERATION_PHASE_ID,
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
                        created_at=PLAYLIST_REGENERATION_GENERATED_AT,
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
            generated_at=PLAYLIST_REGENERATION_GENERATED_AT,
            style_tags_by_track=None,
            critical_warnings_by_track={track_id: () for track_id in scope},
        )
        try:
            projected = project_set_optimizer_result(
                result=self._renderer_safe_result(result),
                display_name_by_track_id=labels,
            )
        except (DesktopSetProposalTransportError, ValueError) as exc:
            raise DesktopPlaylistRegenerationTransportError(
                "playlist_regeneration_projection_failed",
                "The regeneration result could not be projected safely.",
            ) from exc

        alternatives = self._alternatives(
            projected=projected,
            parent_items=parent_items,
            locked=locked,
        )
        candidate_pool_sha256 = hashlib.sha256("\n".join(scope).encode("utf-8")).hexdigest()
        return {
            "schema": PLAYLIST_REGENERATION_SCHEMA,
            "playlist_id": playlist_id,
            "parent_revision_id": parent_id,
            "regeneration_id": str(projected["proposal_id"]),
            "candidate_pool_count": len(scope),
            "candidate_pool_sha256": candidate_pool_sha256,
            "locked_positions": [
                {"order_index": index, "track_id": track_id}
                for index, track_id in locked
            ],
            "alternatives": alternatives,
            "reason_codes": list(projected["reason_codes"]),
            "warning_codes": list(projected["warning_codes"]),
            "budget_exhausted": bool(projected["budget_exhausted"]),
            "missing_evidence_detected": bool(projected["missing_evidence_detected"]),
            "deterministic_ordering": bool(projected["deterministic_ordering"]),
            "playlist_mutation_authorized": False,
            "personal_dj_model_training_authorized": False,
            "production_activation_authorized": False,
        }

    @staticmethod
    def _parent(
        parent_revision: dict[str, object],
    ) -> tuple[str, str, str, tuple[dict[str, object], ...]]:
        if not isinstance(parent_revision, dict):
            raise DesktopPlaylistRegenerationTransportError(
                "invalid_playlist_regeneration_request",
                "The parent revision is invalid.",
            )
        parent_id = parent_revision.get("revision_id")
        playlist_id = parent_revision.get("playlist_id")
        fingerprint = parent_revision.get("content_fingerprint")
        items = parent_revision.get("items")
        if (
            not isinstance(parent_id, str)
            or not isinstance(playlist_id, str)
            or not isinstance(fingerprint, str)
            or len(fingerprint) != 64
            or not isinstance(items, tuple)
            or not 3 <= len(items) <= 8
            or any(not isinstance(item, dict) for item in items)
        ):
            raise DesktopPlaylistRegenerationTransportError(
                "invalid_playlist_regeneration_request",
                "The parent revision is invalid.",
            )
        normalized: list[dict[str, object]] = []
        for index, item in enumerate(items):
            if (
                item.get("order_index") != index
                or not isinstance(item.get("track_id"), str)
                or not isinstance(item.get("display_name"), str)
                or not isinstance(item.get("locked"), bool)
            ):
                raise DesktopPlaylistRegenerationTransportError(
                    "invalid_playlist_regeneration_request",
                    "The parent revision sequence is invalid.",
                )
            normalized.append(item)
        return parent_id, playlist_id, fingerprint, tuple(normalized)

    @staticmethod
    def _request_fingerprint_r1(
        *,
        parent_revision_id: str,
        parent_content_fingerprint: str,
        scope: tuple[str, ...],
        locked: tuple[tuple[int, str], ...],
    ) -> str:
        material = {
            "parent_revision_id": parent_revision_id,
            "parent_content_fingerprint": parent_content_fingerprint,
            "candidate_track_ids": scope,
            "locked_positions": locked,
            "policy_version": PLAYLIST_REGENERATION_POLICY_VERSION,
        }
        encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _alternatives(
        *,
        projected: dict[str, object],
        parent_items: tuple[dict[str, object], ...],
        locked: tuple[tuple[int, str], ...],
    ) -> list[dict[str, object]]:
        raw = projected.get("alternatives")
        if not isinstance(raw, list):
            raise DesktopPlaylistRegenerationTransportError(
                "playlist_regeneration_projection_failed",
                "The regeneration alternatives are invalid.",
            )
        locked_by_position = dict(locked)
        alternatives: list[dict[str, object]] = []
        for alternative in raw:
            if not isinstance(alternative, dict):
                raise DesktopPlaylistRegenerationTransportError(
                    "playlist_regeneration_projection_failed",
                    "The regeneration alternatives are invalid.",
                )
            sequence = alternative.get("sequence")
            if not isinstance(sequence, list) or len(sequence) != len(parent_items):
                raise DesktopPlaylistRegenerationTransportError(
                    "playlist_regeneration_projection_failed",
                    "A regeneration path has the wrong length.",
                )
            safe_sequence: list[dict[str, object]] = []
            for index, step in enumerate(sequence):
                if not isinstance(step, dict):
                    raise DesktopPlaylistRegenerationTransportError(
                        "playlist_regeneration_projection_failed",
                        "A regeneration path is invalid.",
                    )
                track_id = step.get("track_id")
                display_name = step.get("display_name")
                if not isinstance(track_id, str) or not isinstance(display_name, str):
                    raise DesktopPlaylistRegenerationTransportError(
                        "playlist_regeneration_projection_failed",
                        "A regeneration path is invalid.",
                    )
                expected_locked = locked_by_position.get(index)
                if expected_locked is not None and track_id != expected_locked:
                    raise DesktopPlaylistRegenerationTransportError(
                        "playlist_regeneration_projection_failed",
                        "A regeneration path violates an immutable lock.",
                    )
                safe_sequence.append(
                    {
                        "order_index": index,
                        "track_id": track_id,
                        "display_name": display_name,
                        "locked": expected_locked is not None,
                    }
                )
            alternatives.append(
                {
                    "path_id": alternative["path_id"],
                    "rank": alternative["rank"],
                    "sequence": safe_sequence,
                    "objective": alternative["objective"],
                    "explanation_codes": alternative["explanation_codes"],
                }
            )
        return alternatives


__all__ = [
    "DesktopPlaylistRegenerationTransport",
    "DesktopPlaylistRegenerationTransportError",
    "PLAYLIST_REGENERATION_POLICY_VERSION",
    "PLAYLIST_REGENERATION_SCHEMA",
]
