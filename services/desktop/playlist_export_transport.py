from __future__ import annotations

import hashlib
from pathlib import Path

from data.repositories.playlist_revision_repository import PlaylistRevisionRepository
from data.repositories.track_repository import TrackRepository

_MAX_EXPORT_BYTES = 128 * 1024
_FORMAT = "m3u8"
_PREVIEW_SCHEMA = "applaylist-desktop-playlist-export-preview-r1"
_MATERIAL_SCHEMA = "applaylist-desktop-playlist-export-material-r1"


class DesktopPlaylistExportTransportError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DesktopPlaylistExportTransport:
    """Read-only export projection over one exact immutable PlaylistRevision."""

    def __init__(
        self,
        *,
        revisions: PlaylistRevisionRepository | None = None,
        tracks: TrackRepository | None = None,
    ) -> None:
        self.revisions = revisions or PlaylistRevisionRepository()
        self.tracks = tracks or TrackRepository()

    def preview(self, *, revision_id: str) -> dict[str, object]:
        revision = self._revision(revision_id)
        items = self._items(revision)
        return {
            "schema": _PREVIEW_SCHEMA,
            "revision_id": revision["revision_id"],
            "playlist_id": revision["playlist_id"],
            "revision_index": revision["revision_index"],
            "format": _FORMAT,
            "suggested_filename": self._suggested_filename(str(revision["revision_id"])),
            "track_count": len(items),
            "sequence": tuple(
                {
                    "order_index": int(item["order_index"]),
                    "track_id": str(item["track_id"]),
                    "display_name": str(item["display_name"]),
                    "locked": bool(item["locked"]),
                }
                for item in items
            ),
            "personal_dj_model_training_authorized": False,
            "production_activation_authorized": False,
        }

    def material(self, *, revision_id: str) -> dict[str, object]:
        revision = self._revision(revision_id)
        items = self._items(revision)
        lines = ["#EXTM3U"]
        for item in items:
            track_id = str(item["track_id"])
            display_name = self._line_value(str(item["display_name"]), "display name")
            record = self.tracks.get_by_id(track_id)
            if record is None:
                raise DesktopPlaylistExportTransportError(
                    "playlist_export_track_missing",
                    "A revision track is not present in the local track registry.",
                )
            canonical_path = self._canonical_track_path(record.path)
            duration = -1
            if record.duration_seconds is not None and record.duration_seconds >= 0:
                duration = int(round(record.duration_seconds))
            lines.append(f"#EXTINF:{duration},{display_name}")
            lines.append(canonical_path)
        content = "\n".join(lines) + "\n"
        encoded = content.encode("utf-8")
        if len(encoded) > _MAX_EXPORT_BYTES:
            raise DesktopPlaylistExportTransportError(
                "playlist_export_too_large",
                "The export exceeds the bounded M3U8 size limit.",
            )
        digest = hashlib.sha256(encoded).hexdigest()
        return {
            "schema": _MATERIAL_SCHEMA,
            "revision_id": revision["revision_id"],
            "playlist_id": revision["playlist_id"],
            "revision_index": revision["revision_index"],
            "format": _FORMAT,
            "suggested_filename": self._suggested_filename(str(revision["revision_id"])),
            "track_count": len(items),
            "content_utf8": content,
            "content_sha256": digest,
            "byte_count": len(encoded),
            "personal_dj_model_training_authorized": False,
            "production_activation_authorized": False,
        }

    def _revision(self, revision_id: str) -> dict[str, object]:
        token = self._token(revision_id)
        revision = self.revisions.get_revision(token)
        if revision is None:
            raise DesktopPlaylistExportTransportError(
                "playlist_export_revision_not_found",
                "The requested immutable playlist revision was not found.",
            )
        if revision.get("personal_dj_model_training_authorized") is not False:
            raise DesktopPlaylistExportTransportError(
                "playlist_export_revision_invalid",
                "The revision training boundary is invalid.",
            )
        if revision.get("production_activation_authorized") is not False:
            raise DesktopPlaylistExportTransportError(
                "playlist_export_revision_invalid",
                "The revision activation boundary is invalid.",
            )
        return revision

    @staticmethod
    def _items(revision: dict[str, object]) -> tuple[dict[str, object], ...]:
        raw = revision.get("items")
        if not isinstance(raw, (tuple, list)) or not 3 <= len(raw) <= 8:
            raise DesktopPlaylistExportTransportError(
                "playlist_export_revision_invalid",
                "The revision sequence is invalid.",
            )
        result: list[dict[str, object]] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict) or set(item) != {
                "order_index",
                "track_id",
                "display_name",
                "locked",
            }:
                raise DesktopPlaylistExportTransportError(
                    "playlist_export_revision_invalid",
                    "The revision sequence is invalid.",
                )
            if item["order_index"] != index:
                raise DesktopPlaylistExportTransportError(
                    "playlist_export_revision_invalid",
                    "The revision order is invalid.",
                )
            result.append(item)
        return tuple(result)

    @staticmethod
    def _token(value: str) -> str:
        if not isinstance(value, str) or not value or value.strip() != value or len(value) > 256:
            raise DesktopPlaylistExportTransportError(
                "invalid_playlist_export_request",
                "The export revision identity is invalid.",
            )
        if "/" in value or "\\" in value or any(ch.isspace() or ord(ch) < 32 for ch in value):
            raise DesktopPlaylistExportTransportError(
                "invalid_playlist_export_request",
                "The export revision identity is invalid.",
            )
        return value

    @classmethod
    def _canonical_track_path(cls, raw_path: str) -> str:
        value = cls._line_value(raw_path, "track path")
        candidate = Path(value)
        if not candidate.is_absolute():
            raise DesktopPlaylistExportTransportError(
                "playlist_export_track_path_invalid",
                "A revision track path is not absolute.",
            )
        try:
            canonical = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise DesktopPlaylistExportTransportError(
                "playlist_export_track_unavailable",
                "A revision track file is unavailable.",
            ) from exc
        if not canonical.is_file():
            raise DesktopPlaylistExportTransportError(
                "playlist_export_track_unavailable",
                "A revision track file is unavailable.",
            )
        return cls._line_value(str(canonical), "canonical track path")

    @staticmethod
    def _line_value(value: str, label: str) -> str:
        if not isinstance(value, str) or not value or len(value) > 4096:
            raise DesktopPlaylistExportTransportError(
                "playlist_export_content_invalid",
                f"The {label} is invalid.",
            )
        if "\r" in value or "\n" in value or "\x00" in value:
            raise DesktopPlaylistExportTransportError(
                "playlist_export_content_invalid",
                f"The {label} contains a forbidden line break or null byte.",
            )
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            raise DesktopPlaylistExportTransportError(
                "playlist_export_content_invalid",
                f"The {label} contains a forbidden control character.",
            )
        return value

    @staticmethod
    def _suggested_filename(revision_id: str) -> str:
        safe = "".join(ch for ch in revision_id if ch.isascii() and (ch.isalnum() or ch in "_-"))
        if not safe:
            safe = "playlist-revision"
        return f"APPLAYLIST_{safe[:96]}.m3u8"


__all__ = [
    "DesktopPlaylistExportTransport",
    "DesktopPlaylistExportTransportError",
]
