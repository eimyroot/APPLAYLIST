from __future__ import annotations

from http import HTTPStatus

import services.desktop.sidecar as sidecar
from services.desktop.playlist_editor_transport import (
    DesktopPlaylistEditorTransport,
    DesktopPlaylistEditorTransportError,
)

MAX_PLAYLIST_EDITOR_REQUEST_BYTES = 64 * 1024
_INSTALLED = False

_ROUTES = {
    "/v1/playlist/editor/accept": (
        "accept",
        {"track_ids", "seed_track_id", "target_track_count", "proposal_id", "path_id"},
    ),
    "/v1/playlist/editor/reorder": ("reorder", {"revision_id", "ordered_track_ids"}),
    "/v1/playlist/editor/lock": ("lock", {"revision_id", "locked_track_ids"}),
    "/v1/playlist/editor/replace": (
        "replace",
        {"revision_id", "source_track_id", "replacement_track_id"},
    ),
    "/v1/playlist/editor/history": ("history", {"playlist_id"}),
}

_CONFLICT_CODES = {
    "playlist_proposal_stale",
    "playlist_revision_conflict",
    "playlist_revision_not_found",
    "playlist_revision_stale",
    "playlist_revision_membership_changed",
    "playlist_revision_locked_track",
    "playlist_revision_duplicate_track",
    "playlist_revision_noop",
    "playlist_replacement_track_unavailable",
    "playlist_replacement_analysis_missing",
    "playlist_replacement_analysis_failed",
    "playlist_replacement_analysis_incomplete",
}


def install_playlist_editor_sidecar() -> None:
    """Extend the canonical authenticated sidecar with governed editor routes."""
    global _INSTALLED
    if _INSTALLED:
        return

    original_handler = sidecar._SidecarRequestHandler
    original_server = sidecar._SidecarHTTPServer

    class PlaylistEditorRequestHandler(original_handler):
        def do_POST(self) -> None:  # noqa: N802
            route = _ROUTES.get(self.path)
            if route is None:
                super().do_POST()
                return
            self._handle_playlist_editor(route[0], route[1])

        def _handle_playlist_editor(self, operation: str, expected_keys: set[str]) -> None:
            if not self._authorized():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            payload = self._read_json_payload(MAX_PLAYLIST_EDITOR_REQUEST_BYTES)
            if payload is None or set(payload) != expected_keys:
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid_playlist_editor_request"},
                )
                return
            try:
                method = getattr(self.sidecar_server.playlist_editor, operation)
                result = method(**payload)
            except DesktopPlaylistEditorTransportError as exc:
                status = (
                    HTTPStatus.CONFLICT if exc.code in _CONFLICT_CODES else HTTPStatus.BAD_REQUEST
                )
                self._write_json(status, {"error": exc.code})
                return
            except Exception:
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "playlist_editor_operation_failed"},
                )
                return
            self._write_json(HTTPStatus.OK, result)

    sidecar._SidecarRequestHandler = PlaylistEditorRequestHandler

    class PlaylistEditorHTTPServer(original_server):
        def __init__(self, startup: sidecar.SidecarStartup) -> None:
            super().__init__(startup)
            self.playlist_editor = DesktopPlaylistEditorTransport(
                proposal_transport=self.set_proposal,
            )

    sidecar._SidecarHTTPServer = PlaylistEditorHTTPServer
    _INSTALLED = True


__all__ = ["MAX_PLAYLIST_EDITOR_REQUEST_BYTES", "install_playlist_editor_sidecar"]
