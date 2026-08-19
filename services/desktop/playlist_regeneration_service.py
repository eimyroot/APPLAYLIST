from __future__ import annotations

from collections.abc import Sequence

from data.repositories.playlist_revision_repository import (
    PlaylistRevisionRepository,
    PlaylistRevisionRepositoryError,
)
from services.desktop.playlist_regeneration_transport import (
    DesktopPlaylistRegenerationTransport,
    DesktopPlaylistRegenerationTransportError,
)


class DesktopPlaylistRegenerationServiceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DesktopPlaylistRegenerationService:
    """Governed preview/apply boundary for Bundle 62 regeneration around locks."""

    def __init__(
        self,
        *,
        generator: DesktopPlaylistRegenerationTransport | None = None,
        revision_repository: PlaylistRevisionRepository | None = None,
    ) -> None:
        self._generator = generator or DesktopPlaylistRegenerationTransport()
        self._revisions = revision_repository or PlaylistRevisionRepository()

    def preview(
        self,
        *,
        revision_id: str,
        candidate_track_ids: Sequence[str],
    ) -> dict[str, object]:
        parent = self._required_current(revision_id)
        try:
            return self._generator.generate(
                parent_revision=parent,
                candidate_track_ids=candidate_track_ids,
            )
        except DesktopPlaylistRegenerationTransportError as exc:
            raise DesktopPlaylistRegenerationServiceError(exc.code, exc.message) from exc

    def apply(
        self,
        *,
        revision_id: str,
        candidate_track_ids: Sequence[str],
        regeneration_id: str,
        path_id: str,
    ) -> dict[str, object]:
        parent = self._required_current(revision_id)
        expected_regeneration = self._token(regeneration_id, "regeneration_id")
        expected_path = self._token(path_id, "path_id")
        try:
            preview = self._generator.generate(
                parent_revision=parent,
                candidate_track_ids=candidate_track_ids,
            )
        except DesktopPlaylistRegenerationTransportError as exc:
            raise DesktopPlaylistRegenerationServiceError(
                "playlist_regeneration_stale",
                "The regeneration preview can no longer be reproduced from current evidence.",
            ) from exc
        if preview.get("regeneration_id") != expected_regeneration:
            raise DesktopPlaylistRegenerationServiceError(
                "playlist_regeneration_stale",
                "The regeneration identity no longer matches current evidence or locks.",
            )
        alternatives = preview.get("alternatives")
        if not isinstance(alternatives, list):
            raise DesktopPlaylistRegenerationServiceError(
                "playlist_regeneration_stale",
                "The regeneration alternatives are unavailable.",
            )
        selected = next(
            (
                item
                for item in alternatives
                if isinstance(item, dict) and item.get("path_id") == expected_path
            ),
            None,
        )
        if selected is None:
            raise DesktopPlaylistRegenerationServiceError(
                "playlist_regeneration_stale",
                "The selected regeneration path no longer exists.",
            )
        sequence = selected.get("sequence")
        rank = selected.get("rank")
        if not isinstance(sequence, list) or not isinstance(rank, int):
            raise DesktopPlaylistRegenerationServiceError(
                "playlist_regeneration_stale",
                "The selected regeneration path is invalid.",
            )
        items: list[tuple[str, str, bool]] = []
        for index, step in enumerate(sequence):
            if not isinstance(step, dict):
                raise DesktopPlaylistRegenerationServiceError(
                    "playlist_regeneration_stale",
                    "The selected regeneration path is invalid.",
                )
            track_id = step.get("track_id")
            display_name = step.get("display_name")
            locked = step.get("locked")
            if (
                step.get("order_index") != index
                or not isinstance(track_id, str)
                or not isinstance(display_name, str)
                or not isinstance(locked, bool)
            ):
                raise DesktopPlaylistRegenerationServiceError(
                    "playlist_regeneration_stale",
                    "The selected regeneration path is invalid.",
                )
            items.append((track_id, display_name, locked))

        parent_items = parent.get("items")
        if not isinstance(parent_items, tuple):
            raise DesktopPlaylistRegenerationServiceError(
                "playlist_regeneration_stale",
                "The current playlist revision is invalid.",
            )
        parent_signature = tuple(
            (str(item["track_id"]), str(item["display_name"]), bool(item["locked"]))
            for item in parent_items
        )
        if tuple(items) == parent_signature:
            raise DesktopPlaylistRegenerationServiceError(
                "playlist_revision_noop",
                "Regeneration must change at least one unlocked playlist position.",
            )

        metadata = {
            "regeneration_id": expected_regeneration,
            "path_id": expected_path,
            "selected_rank": rank,
            "candidate_pool_count": int(preview["candidate_pool_count"]),
            "candidate_pool_sha256": str(preview["candidate_pool_sha256"]),
            "locked_positions": list(preview["locked_positions"]),
        }
        try:
            revision = self._revisions.append_child(
                parent_revision_id=str(parent["revision_id"]),
                operation="regenerate",
                items=tuple(items),
                operation_metadata=metadata,
            )
        except PlaylistRevisionRepositoryError as exc:
            raise self._repository_error(exc) from exc
        return self._revision_dto(revision)

    def _required_current(self, revision_id: str) -> dict[str, object]:
        normalized = self._token(revision_id, "revision_id")
        try:
            parent = self._revisions.get_revision(normalized)
        except PlaylistRevisionRepositoryError as exc:
            raise self._repository_error(exc) from exc
        if parent is None:
            raise DesktopPlaylistRegenerationServiceError(
                "playlist_revision_not_found",
                "The playlist revision does not exist.",
            )
        current = self._revisions.current_revision(str(parent["playlist_id"]))
        if current is None or str(current["revision_id"]) != str(parent["revision_id"]):
            raise DesktopPlaylistRegenerationServiceError(
                "playlist_revision_stale",
                "The requested playlist revision is not current.",
            )
        return parent

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
    def _repository_error(
        exc: PlaylistRevisionRepositoryError,
    ) -> DesktopPlaylistRegenerationServiceError:
        return DesktopPlaylistRegenerationServiceError(exc.code, exc.message)

    @staticmethod
    def _token(value: str, field: str) -> str:
        if not isinstance(value, str):
            raise DesktopPlaylistRegenerationServiceError(
                "invalid_playlist_regeneration_request",
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
            raise DesktopPlaylistRegenerationServiceError(
                "invalid_playlist_regeneration_request",
                f"{field} is invalid.",
            )
        return normalized


__all__ = [
    "DesktopPlaylistRegenerationService",
    "DesktopPlaylistRegenerationServiceError",
]
