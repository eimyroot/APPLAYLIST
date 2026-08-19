from __future__ import annotations

from dataclasses import asdict
from typing import Any

from core.intelligence.music_dna import Confidence
from core.intelligence.transition_contract import TransitionAssessment
from data.repositories.music_intelligence_repository import MusicIntelligenceRepository
from data.repositories.playlist_revision_repository import (
    PlaylistRevisionRepository,
    PlaylistRevisionRepositoryError,
)
from data.repositories.transition_evidence_index import TransitionEvidenceIndex


class DesktopTransitionInspectorError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DesktopTransitionInspectorTransport:
    """Read-only inspection of persisted TransitionAssessment evidence for one revision edge."""

    def __init__(
        self,
        *,
        revisions: PlaylistRevisionRepository | None = None,
        intelligence: MusicIntelligenceRepository | None = None,
        evidence_index: TransitionEvidenceIndex | None = None,
    ) -> None:
        self.revisions = revisions or PlaylistRevisionRepository()
        self.intelligence = intelligence or MusicIntelligenceRepository()
        self.evidence_index = evidence_index or TransitionEvidenceIndex(repository=self.intelligence)

    def inspect(self, *, revision_id: str, pair_index: int) -> dict[str, object]:
        revision = self._revision(revision_id)
        sequence = tuple(revision["items"])
        if not isinstance(pair_index, int) or isinstance(pair_index, bool) or not 0 <= pair_index < len(sequence) - 1:
            raise DesktopTransitionInspectorError(
                "invalid_transition_inspection_request",
                "pair_index must identify an adjacent pair in the selected revision.",
            )
        source = sequence[pair_index]
        target = sequence[pair_index + 1]
        source_track_id = self._token(str(source["track_id"]))
        target_track_id = self._token(str(target["track_id"]))
        snapshots = self.evidence_index.list_pair_snapshots(
            source_track_id=source_track_id,
            target_track_id=target_track_id,
        )
        metadata = tuple(self._snapshot_metadata(item) for item in snapshots)
        base: dict[str, object] = {
            "schema": "applaylist-desktop-transition-inspection-r1",
            "revision_id": str(revision["revision_id"]),
            "playlist_id": str(revision["playlist_id"]),
            "revision_index": int(revision["revision_index"]),
            "pair_index": pair_index,
            "source": self._revision_item(source),
            "target": self._revision_item(target),
            "available_snapshots": metadata,
            "personal_dj_model_training_authorized": False,
            "production_activation_authorized": False,
            "transition_recomputation_authorized": False,
            "playlist_mutation_authorized": False,
        }
        if not snapshots:
            return {
                **base,
                "state": "missing",
                "selected_snapshot_id": None,
                "assessment": None,
            }

        selected = snapshots[0]
        snapshot_id = self._token(str(selected["snapshot_id"]))
        assessment = self.intelligence.get_transition_snapshot(snapshot_id)
        if assessment is None:
            raise DesktopTransitionInspectorError(
                "transition_inspection_snapshot_missing",
                "The selected persisted transition snapshot is unavailable.",
            )
        self._verify_pair(assessment, source_track_id, target_track_id)
        return {
            **base,
            "state": "present",
            "selected_snapshot_id": snapshot_id,
            "assessment": self._assessment(assessment),
        }

    def _revision(self, revision_id: str) -> dict[str, object]:
        try:
            revision = self.revisions.get_revision(revision_id)
        except PlaylistRevisionRepositoryError as exc:
            raise DesktopTransitionInspectorError(
                "invalid_transition_inspection_request",
                "The selected revision identity is invalid.",
            ) from exc
        if revision is None:
            raise DesktopTransitionInspectorError(
                "transition_inspection_revision_not_found",
                "The selected playlist revision was not found.",
            )
        items = revision.get("items")
        if not isinstance(items, tuple) or not 3 <= len(items) <= 8:
            raise DesktopTransitionInspectorError(
                "transition_inspection_revision_invalid",
                "The selected playlist revision is invalid.",
            )
        return revision

    @classmethod
    def _revision_item(cls, item: object) -> dict[str, object]:
        if not isinstance(item, dict):
            raise DesktopTransitionInspectorError(
                "transition_inspection_revision_invalid",
                "The selected playlist revision is invalid.",
            )
        return {
            "order_index": int(item["order_index"]),
            "track_id": cls._token(str(item["track_id"])),
            "display_name": cls._label(str(item["display_name"])),
            "locked": bool(item["locked"]),
        }

    @classmethod
    def _snapshot_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        return {
            "snapshot_id": cls._token(str(value["snapshot_id"])),
            "transition_id": cls._token(str(value["transition_id"])),
            "source_segment_id": cls._token(str(value["source_segment_id"])),
            "target_segment_id": cls._token(str(value["target_segment_id"])),
            "assessment_version": cls._token(str(value["assessment_version"])),
            "policy_version": cls._token(str(value["policy_version"])),
            "context_id": cls._token(str(value["context_id"])),
            "context_version": cls._token(str(value["context_version"])),
            "payload_sha256": cls._digest(str(value["payload_sha256"])),
            "created_at": cls._text(str(value["created_at"]), limit=64),
        }

    @classmethod
    def _assessment(cls, value: TransitionAssessment) -> dict[str, object]:
        identity = value.identity
        projection = value.contextual_projection
        return {
            "transition_id": cls._token(identity.transition_id),
            "source_segment_id": cls._token(identity.source_segment_id),
            "target_segment_id": cls._token(identity.target_segment_id),
            "assessment_version": cls._token(identity.assessment_version),
            "policy_version": cls._token(identity.policy_version),
            "music_dna_revision_refs": [cls._token(item) for item in identity.music_dna_revision_refs],
            "created_at": cls._text(identity.created_at, limit=64),
            "compatibility": cls._json_safe(asdict(value.compatibility_vector)),
            "risk": cls._json_safe(asdict(value.risk_vector)),
            "cost": cls._json_safe(asdict(value.cost_vector)),
            "energy_effect": {
                "source_energy_state": value.energy_effect.source_energy_state,
                "target_energy_state": value.energy_effect.target_energy_state,
                "delta": value.energy_effect.delta,
                "local_curve_alignment": value.energy_effect.local_curve_alignment,
                "direction": value.energy_effect.direction.value,
                "confidence": cls._confidence(value.energy_effect.confidence),
            },
            "candidate_strategies": [
                {
                    "strategy": item.strategy.value,
                    "suitability": item.suitability,
                    "required_capabilities": [cls._token(capability) for capability in item.required_capabilities],
                    "explanation_codes": [cls._token(code) for code in item.explanation_codes],
                }
                for item in value.candidate_strategies
            ],
            "preferred_strategy": value.preferred_strategy.value if value.preferred_strategy else None,
            "usable_window": {
                "source_start_seconds": value.usable_window.source_start_seconds,
                "source_end_seconds": value.usable_window.source_end_seconds,
                "target_start_seconds": value.usable_window.target_start_seconds,
                "target_end_seconds": value.usable_window.target_end_seconds,
                "source_bar_count": value.usable_window.source_bar_count,
                "target_bar_count": value.usable_window.target_bar_count,
                "confidence": cls._confidence(value.usable_window.confidence),
            },
            "contextual_projection": {
                "context_id": cls._token(projection.context_id),
                "context_version": cls._token(projection.context_version),
                "score": projection.score,
                "blocked_reasons": [cls._token(item) for item in projection.blocked_reasons],
                "rank_features": [cls._token(item) for item in projection.rank_features],
                "confidence": cls._confidence(projection.confidence),
                "explanation_codes": [cls._token(item) for item in projection.explanation_codes],
            },
            "confidence": cls._confidence(value.confidence),
            "explanations": [
                {
                    "code": cls._token(item.code),
                    "severity": cls._token(item.severity),
                    "dimension": cls._token(item.dimension),
                    "evidence_refs": [cls._token(ref) for ref in item.evidence_refs],
                    "confidence": cls._confidence(item.confidence),
                }
                for item in value.explanations
            ],
            "evidence_refs": [cls._token(item) for item in value.evidence_refs],
            "warnings": [cls._text(item, limit=512) for item in value.warnings],
        }

    @staticmethod
    def _confidence(value: Confidence) -> dict[str, object]:
        return {
            "score": value.score,
            "calibration_state": value.calibration_state.value,
            "evidence_count": value.evidence_count,
            "disagreement": value.disagreement,
        }

    @staticmethod
    def _json_safe(value: dict[str, Any]) -> dict[str, object]:
        return {str(key): item for key, item in value.items()}

    @staticmethod
    def _verify_pair(assessment: TransitionAssessment, source_track_id: str, target_track_id: str) -> None:
        if (
            assessment.identity.source_track_id != source_track_id
            or assessment.identity.target_track_id != target_track_id
        ):
            raise DesktopTransitionInspectorError(
                "transition_inspection_identity_mismatch",
                "Persisted transition evidence does not match the selected revision pair.",
            )

    @staticmethod
    def _token(value: str) -> str:
        if not isinstance(value, str) or not value or value.strip() != value or len(value) > 256:
            raise DesktopTransitionInspectorError("transition_inspection_projection_invalid", "Unsafe identity token.")
        if "/" in value or "\\" in value or any(ch.isspace() or ord(ch) < 32 for ch in value):
            raise DesktopTransitionInspectorError("transition_inspection_projection_invalid", "Unsafe identity token.")
        return value

    @staticmethod
    def _label(value: str) -> str:
        if not isinstance(value, str) or not value or value.strip() != value or len(value) > 512:
            raise DesktopTransitionInspectorError("transition_inspection_projection_invalid", "Unsafe display label.")
        if value.startswith(("/", "\\\\")) or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            raise DesktopTransitionInspectorError("transition_inspection_projection_invalid", "Unsafe display label.")
        if len(value) >= 3 and value[0].isalpha() and value[1:3] in {":\\", ":/"}:
            raise DesktopTransitionInspectorError("transition_inspection_projection_invalid", "Unsafe display label.")
        return value

    @staticmethod
    def _text(value: str, *, limit: int) -> str:
        if not isinstance(value, str) or len(value) > limit or any(ord(ch) < 32 and ch not in "\t" for ch in value):
            raise DesktopTransitionInspectorError("transition_inspection_projection_invalid", "Unsafe text value.")
        return value

    @staticmethod
    def _digest(value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise DesktopTransitionInspectorError("transition_inspection_projection_invalid", "Invalid evidence digest.")
        return value


__all__ = ["DesktopTransitionInspectorError", "DesktopTransitionInspectorTransport"]
