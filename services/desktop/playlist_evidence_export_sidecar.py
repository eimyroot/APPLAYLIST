from __future__ import annotations

from http import HTTPStatus

import services.desktop.sidecar as sidecar
from services.desktop.playlist_evidence_export_transport import (
    DesktopPlaylistEvidenceExportError,
    DesktopPlaylistEvidenceExportTransport,
)

MAX_PLAYLIST_EVIDENCE_EXPORT_REQUEST_BYTES = 8 * 1024
_INSTALLED = False

_ROUTES = {
    "/v1/playlist/evidence/preview": "preview",
    "/v1/playlist/evidence/material": "material",
}

_CONFLICT_CODES = {
    "playlist_evidence_revision_not_found",
    "playlist_export_revision_not_found",
    "playlist_export_track_missing",
    "playlist_export_track_unavailable",
}


def install_playlist_evidence_export_sidecar() -> None:
    """Extend the authenticated sidecar with deterministic JSON evidence export routes."""
    global _INSTALLED
    if _INSTALLED:
        return

    original_handler = sidecar._SidecarRequestHandler
    original_server = sidecar._SidecarHTTPServer

    class PlaylistEvidenceExportRequestHandler(original_handler):
        def do_POST(self) -> None:  # noqa: N802
            operation = _ROUTES.get(self.path)
            if operation is None:
                super().do_POST()
                return
            self._handle_playlist_evidence_export(operation)

        def _handle_playlist_evidence_export(self, operation: str) -> None:
            if not self._authorized():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            payload = self._read_json_payload(MAX_PLAYLIST_EVIDENCE_EXPORT_REQUEST_BYTES)
            if payload is None or set(payload) != {"revision_id"}:
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid_playlist_evidence_export_request"},
                )
                return
            try:
                method = getattr(self.sidecar_server.playlist_evidence_export, operation)
                result = method(revision_id=payload["revision_id"])
            except DesktopPlaylistEvidenceExportError as exc:
                status = HTTPStatus.CONFLICT if exc.code in _CONFLICT_CODES else HTTPStatus.BAD_REQUEST
                self._write_json(status, {"error": exc.code})
                return
            except Exception:
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "playlist_evidence_export_operation_failed"},
                )
                return
            self._write_json(HTTPStatus.OK, result)

    sidecar._SidecarRequestHandler = PlaylistEvidenceExportRequestHandler

    class PlaylistEvidenceExportHTTPServer(original_server):
        def __init__(self, startup: sidecar.SidecarStartup) -> None:
            super().__init__(startup)
            self.playlist_evidence_export = DesktopPlaylistEvidenceExportTransport()

    sidecar._SidecarHTTPServer = PlaylistEvidenceExportHTTPServer
    _INSTALLED = True


__all__ = [
    "MAX_PLAYLIST_EVIDENCE_EXPORT_REQUEST_BYTES",
    "install_playlist_evidence_export_sidecar",
]
