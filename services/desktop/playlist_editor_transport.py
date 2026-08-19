from __future__ import annotations

from collections.abc import Sequence

from data.repositories.analysis_evidence_repository import AnalysisEvidenceRepository
from data.repositories.playlist_revision_repository import (
    PlaylistRevisionRepository,
    PlaylistRevisionRepositoryError,
)
from data.repositories.track_repository import TrackRepository
from services.desktop.set_proposal_transport import (
    DesktopSetProposalTransport,
    DesktopSetProposalTransportError,
)

_MAX_HISTORY = 100


class DesktopPlaylistEditorTransportError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DesktopPlaylistEditorTransport:
    """Governed manual editor over immutable append-only playlist revisions."""

    def __init__(
        self,
        *,
        proposal_transport: DesktopSetProposalTransport | None = None,
        revision_repository: PlaylistRevisionRepository | None = None,
        evidence_repository: AnalysisEvidenceRepository | None = None,
        track_repository: TrackRepository | None = None,
    ) -> None:
        self._proposals = proposal_transport or DesktopSetProposalTransport()
        self._revisions = revision_repository or PlaylistRevisionRepository()
        self._evidence = evidence_repository or AnalysisEvidenceRepository()
        self._tracks = track_repository or TrackRepository()

    def accept(
        self,
        *,
        track_ids: Sequence[str],
        seed_track_id: str,
        target_track_count: int,
        proposal_id: str,
        path_id: str,
    ) -> dict[str, object]:
        expected_proposal_id = self._token(proposal_id, "proposal_id")
        expected_path_id = self._token(path_id, "path_id")
        try:
            proposal = self._proposals.generate(
                track_ids=track_ids,
                seed_track_id=seed_track_id,
                target_track_count=target_track_count,
            )
        except DesktopSetProposalTransportError as exc:
            raise DesktopPlaylistEditorTransportError(
                "playlist_proposal_stale",
                "The proposal can no longer be verified against current evidence.",
            ) from exc
        if proposal.get("proposal_id") != expected_proposal_id:
            raise DesktopPlaylistEditorTransportError(
                "playlist_proposal_stale",
                "The proposal identity no longer matches current evidence.",
            )
        alternatives = proposal.get("alternatives")
        if not isinstance(alternatives, list):
            raise DesktopPlaylistEditorTransportError(
                "playlist_proposal_stale",
                "The proposal alternatives are unavailable.",
            )
        selected = next(
            (
                item
                for item in alternatives
                if isinstance(item, dict) and item.get("path_id") == expected_path_id
            ),
            None,
        )
        if selected is None:
            raise DesktopPlaylistEditorTransportError(
                "playlist_proposal_stale",
                "The selected proposal path no longer matches current evidence.",
            )
        sequence = selected.get("sequence")
        rank = selected.get("rank")
        if not isinstance(sequence, list) or not isinstance(rank, int):
            raise DesktopPlaylistEditorTransportError(
                "playlist_proposal_stale",
                "The selected proposal path is invalid.",
            )
        items: list[tuple[str, str]] = []
        for step in sequence:
            if not isinstance(step, dict):
                raise DesktopPlaylistEditorTransportError(
                    "playlist_proposal_stale",
                    "The selected proposal path is invalid.",
                )
            track_id = step.get("track_id")
            display_name = step.get("display_name")
            if not isinstance(track_id, str) or not isinstance(display_name, str):
                raise DesktopPlaylistEditorTransportError(
                    "playlist_proposal_stale",
                    "The selected proposal path is invalid.",
                )
            items.append((track_id, display_name))
        try:
            revision = self._revisions.append_root(
                source_proposal_id=expected_proposal_id,
                source_path_id=expected_path_id,
                items=items,
                operation_metadata={"accepted_rank": rank},
            )
        except PlaylistRevisionRepositoryError as exc:
            raise self._repository_error(exc) from exc
        return self._revision_dto(revision)

    def reorder(
        self,
        *,
        revision_id: str,
        ordered_track_ids: Sequence[str],
    ) -> dict[str, object]:
        parent = self._required_current(revision_id)
        requested = self._track_id_list(ordered_track_ids, expected_count=len(parent["items"]))
        existing_ids = tuple(str(item["track_id"]) for item in parent["items"])
        if set(requested) != set(existing_ids):
            raise DesktopPlaylistEditorTransportError(
                "playlist_revision_membership_changed",
                "Reorder must preserve exact playlist membership.",
            )
        if requested == existing_ids:
            raise DesktopPlaylistEditorTransportError(
                "playlist_revision_noop",
                "Reorder must change the playlist order.",
            )
        old_positions = {track_id: index for index, track_id in enumerate(existing_ids)}
        new_positions = {track_id: index for index, track_id in enumerate(requested)}
        locked = {str(item["track_id"]) for item in parent["items"] if bool(item["locked"])}
        if any(old_positions[track_id] != new_positions[track_id] for track_id in locked):
            raise DesktopPlaylistEditorTransportError(
                "playlist_revision_locked_track",
                "Locked tracks cannot move during reorder.",
            )
        by_id = {str(item["track_id"]): item for item in parent["items"]}
        items = tuple(
            (track_id, str(by_id[track_id]["display_name"]), bool(by_id[track_id]["locked"]))
            for track_id in requested
        )
        return self._append_child(
            parent=parent,
            operation="reorder",
            items=items,
            metadata={"ordered_track_ids": list(requested)},
        )

    def lock(
        self,
        *,
        revision_id: str,
        locked_track_ids: Sequence[str],
    ) -> dict[str, object]:
        parent = self._required_current(revision_id)
        requested = self._track_id_list(
            locked_track_ids,
            expected_count=None,
            allow_empty=True,
            maximum=len(parent["items"]),
        )
        members = {str(item["track_id"]) for item in parent["items"]}
        if not set(requested).issubset(members):
            raise DesktopPlaylistEditorTransportError(
                "playlist_revision_membership_changed",
                "Only playlist members may be locked.",
            )
        previous = tuple(str(item["track_id"]) for item in parent["items"] if bool(item["locked"]))
        requested_set = set(requested)
        normalized_requested = tuple(
            str(item["track_id"]) for item in parent["items"] if str(item["track_id"]) in requested_set
        )
        if normalized_requested == previous:
            raise DesktopPlaylistEditorTransportError(
                "playlist_revision_noop",
                "Lock operation must change the lock set.",
            )
        items = tuple(
            (str(item["track_id"]), str(item["display_name"]), str(item["track_id"]) in requested_set)
            for item in parent["items"]
        )
        return self._append_child(
            parent=parent,
            operation="lock",
            items=items,
            metadata={"locked_track_ids": list(normalized_requested)},
        )

    def replace(
        self,
        *,
        revision_id: str,
        source_track_id: str,
        replacement_track_id: str,
    ) -> dict[str, object]:
        parent = self._required_current(revision_id)
        source = self._track_id(source_track_id)
        replacement = self._track_id(replacement_track_id)
        if source == replacement:
            raise DesktopPlaylistEditorTransportError(
                "playlist_revision_noop",
                "Replacement track must be different from the source track.",
            )
        by_id = {str(item["track_id"]): item for item in parent["items"]}
        source_item = by_id.get(source)
        if source_item is None:
            raise DesktopPlaylistEditorTransportError(
                "playlist_revision_membership_changed",
                "The source track is not in the current revision.",
            )
        if bool(source_item["locked"]):
            raise DesktopPlaylistEditorTransportError(
                "playlist_revision_locked_track",
                "Locked tracks cannot be replaced.",
            )
        if replacement in by_id:
            raise DesktopPlaylistEditorTransportError(
                "playlist_revision_duplicate_track",
                "Replacement would create a duplicate track.",
            )
        display_name = self._replacement_display_name(replacement)
        items = tuple(
            (
                replacement if str(item["track_id"]) == source else str(item["track_id"]),
                display_name if str(item["track_id"]) == source else str(item["display_name"]),
                False if str(item["track_id"]) == source else bool(item["locked"]),
            )
            for item in parent["items"]
        )
        return self._append_child(
            parent=parent,
            operation="replace",
            items=items,
            metadata={
                "source_track_id": source,
                "replacement_track_id": replacement,
            },
        )

    def history(self, *, playlist_id: str) -> dict[str, object]:
        normalized = self._token(playlist_id, "playlist_id")
        revisions = self._revisions.list_revisions(normalized, limit=_MAX_HISTORY)
        if not revisions:
            raise DesktopPlaylistEditorTransportError(
                "playlist_revision_not_found",
                "Playlist revision history was not found.",
            )
        current = revisions[-1]
        return {
            "schema": "applaylist-desktop-playlist-history-r1",
            "playlist_id": normalized,
            "current_revision_id": str(current["revision_id"]),
            "revisions": [self._revision_dto(item) for item in revisions],
            "history_truncated": self._revisions.count_revisions(normalized) > len(revisions),
            "personal_dj_model_training_authorized": False,
            "production_activation_authorized": False,
        }

    def _required_current(self, revision_id: str) -> dict[str, object]:
        normalized = self._token(revision_id, "revision_id")
        try:
            parent = self._revisions.get_revision(normalized)
        except PlaylistRevisionRepositoryError as exc:
            raise self._repository_error(exc) from exc
        if parent is None:
            raise DesktopPlaylistEditorTransportError(
                "playlist_revision_not_found",
                "The playlist revision does not exist.",
            )
        current = self._revisions.current_revision(str(parent["playlist_id"]))
        if current is None or str(current["revision_id"]) != str(parent["revision_id"]):
            raise DesktopPlaylistEditorTransportError(
                "playlist_revision_stale",
                "The requested revision is not current.",
            )
        return parent

    def _append_child(
        self,
        *,
        parent: dict[str, object],
        operation: str,
        items: Sequence[tuple[str, str, bool]],
        metadata: dict[str, object],
    ) -> dict[str, object]:
        try:
            revision = self._revisions.append_child(
                parent_revision_id=str(parent["revision_id"]),
                operation=operation,
                items=items,
                operation_metadata=metadata,
            )
        except PlaylistRevisionRepositoryError as exc:
            raise self._repository_error(exc) from exc
        return self._revision_dto(revision)

    def _replacement_display_name(self, track_id: str) -> str:
        track = self._tracks.get_by_id(track_id)
        if track is None:
            raise DesktopPlaylistEditorTransportError(
                "playlist_replacement_track_unavailable",
                "The replacement track is unavailable in the local library.",
            )
        attempt = self._evidence.latest_evidence_for_track(track_id)
        if attempt is None:
            raise DesktopPlaylistEditorTransportError(
                "playlist_replacement_analysis_missing",
                "The replacement track has no analysis evidence.",
            )
        if attempt.status != "succeeded":
            raise DesktopPlaylistEditorTransportError(
                "playlist_replacement_analysis_failed",
                "The replacement track's latest analysis failed.",
            )
        success = self._evidence.latest_success_for_track(track_id)
        if success is None or success.evidence_id != attempt.evidence_id:
            raise DesktopPlaylistEditorTransportError(
                "playlist_replacement_analysis_failed",
                "The replacement track has no current successful analysis.",
            )
        if (
            success.provider_version is None
            or success.algorithm_version is None
            or success.duration_seconds is None
            or success.duration_seconds <= 0.0
            or success.bpm is None
            or success.energy is None
        ):
            raise DesktopPlaylistEditorTransportError(
                "playlist_replacement_analysis_incomplete",
                "The replacement track lacks required analysis evidence.",
            )
        title = track.title.strip() if isinstance(track.title, str) and track.title.strip() else track_id
        artist = (
            track.artist.strip()
            if isinstance(track.artist, str) and track.artist.strip()
            else None
        )
        return f"{artist} — {title}" if artist is not None else title

    @staticmethod
    def _revision_dto(record: dict[str, object]) -> dict[str, object]:
        return {
            "schema": "applaylist-desktop-playlist-revision-r1",
            "playlist_id": str(record["playlist_id"]),
            "revision_id": str(record["revision_id"]),
            "parent_revision_id": record["parent_revision_id"],
            "revision_index": int(record["revision_index"]),
            "source_proposal_id": str(record["source_proposal_id"]),
            "source_path_id": str(record["source_path_id"]),
            "operation": str(record["operation"]),
            "content_fingerprint": str(record["content_fingerprint"]),
            "created_at": str(record["created_at"]),
            "sequence": [
                {
                    "order_index": int(item["order_index"]),
                    "track_id": str(item["track_id"]),
                    "display_name": str(item["display_name"]),
                    "locked": bool(item["locked"]),
                }
                for item in record["items"]
            ],
            "personal_dj_model_training_authorized": False,
            "production_activation_authorized": False,
        }

    @staticmethod
    def _repository_error(exc: PlaylistRevisionRepositoryError) -> DesktopPlaylistEditorTransportError:
        return DesktopPlaylistEditorTransportError(exc.code, exc.message)

    @staticmethod
    def _token(value: str, field: str) -> str:
        if not isinstance(value, str):
            raise DesktopPlaylistEditorTransportError(
                "invalid_playlist_editor_request",
                f"{field} must be text.",
            )
        normalized = value.strip()
        if (
            not normalized
            or normalized != value
            or len(normalized) > 256
            or "/" in normalized
            or "\\" in normalized
            or any(character.isspace() or ord(character) < 32 for character in normalized)
        ):
            raise DesktopPlaylistEditorTransportError(
                "invalid_playlist_editor_request",
                f"{field} is invalid.",
            )
        return normalized

    @classmethod
    def _track_id(cls, value: str) -> str:
        return cls._token(value, "track_id")

    @classmethod
    def _track_id_list(
        cls,
        values: Sequence[str],
        *,
        expected_count: int | None,
        allow_empty: bool = False,
        maximum: int = 8,
    ) -> tuple[str, ...]:
        if isinstance(values, (str, bytes)):
            raise DesktopPlaylistEditorTransportError(
                "invalid_playlist_editor_request",
                "Track IDs must be a bounded list.",
            )
        normalized = tuple(cls._track_id(item) for item in values)
        if len(normalized) > maximum or (not allow_empty and not normalized):
            raise DesktopPlaylistEditorTransportError(
                "invalid_playlist_editor_request",
                "Track ID list is outside the allowed bounds.",
            )
        if expected_count is not None and len(normalized) != expected_count:
            raise DesktopPlaylistEditorTransportError(
                "playlist_revision_membership_changed",
                "Track ID list does not match the current revision size.",
            )
        if len(set(normalized)) != len(normalized):
            raise DesktopPlaylistEditorTransportError(
                "playlist_revision_duplicate_track",
                "Track ID list contains duplicates.",
            )
        return normalized


__all__ = ["DesktopPlaylistEditorTransport", "DesktopPlaylistEditorTransportError"]
