from __future__ import annotations

from http import HTTPStatus

import services.desktop.sidecar as sidecar
from services.desktop.playlist_vendor_interop_transport import (
    DesktopPlaylistVendorInteropError,
    DesktopPlaylistVendorInteropTransport,
)

MAX_PLAYLIST_VENDOR_INTEROP_REQUEST_BYTES = 8 * 1024
_INSTALLED = False

_ROUTES = {
    "/v1/playlist/vendor/preview": "preview",
    "/v1/playlist/vendor/rekordbox/material": "rekordbox_material",
}

_CONFLICT_CODES = {
    "playlist_export_revision_not_found",
    "playlist_export_track_missing",
    "playlist_export_track_unavailable",
}


def install_playlist_vendor_interop_sidecar() -> None:
    """Extend the authenticated sidecar with bounded vendor handoff routes."""
    global _INSTALLED
    if _INSTALLED:
        return

    original_handler = sidecar._SidecarRequestHandler
    original_server = sidecar._SidecarHTTPServer

    class PlaylistVendorInteropRequestHandler(original_handler):
        def do_POST(self) -> None:  # noqa: N802
            operation = _ROUTES.get(self.path)
            if operation is None:
                super().do_POST()
                return
            self._handle_playlist_vendor_interop(operation)

        def _handle_playlist_vendor_interop(self, operation: str) -> None:
            if not self._authorized():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            payload = self._read_json_payload(MAX_PLAYLIST_VENDOR_INTEROP_REQUEST_BYTES)
            if payload is None or set(payload) != {"revision_id"}:
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid_playlist_vendor_interop_request"},
                )
                return
            try:
                method = getattr(self.sidecar_server.playlist_vendor_interop, operation)
                result = method(revision_id=payload["revision_id"])
            except DesktopPlaylistVendorInteropError as exc:
                status = HTTPStatus.CONFLICT if exc.code in _CONFLICT_CODES else HTTPStatus.BAD_REQUEST
                self._write_json(status, {"error": exc.code})
                return
            except Exception:
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "playlist_vendor_interop_operation_failed"},
                )
                return
            self._write_json(HTTPStatus.OK, result)

    sidecar._SidecarRequestHandler = PlaylistVendorInteropRequestHandler

    class PlaylistVendorInteropHTTPServer(original_server):
        def __init__(self, startup: sidecar.SidecarStartup) -> None:
            super().__init__(startup)
            self.playlist_vendor_interop = DesktopPlaylistVendorInteropTransport()

    sidecar._SidecarHTTPServer = PlaylistVendorInteropHTTPServer
    _INSTALLED = True


__all__ = [
    "MAX_PLAYLIST_VENDOR_INTEROP_REQUEST_BYTES",
    "install_playlist_vendor_interop_sidecar",
]
