from __future__ import annotations

from http import HTTPStatus

import services.desktop.sidecar as sidecar
from services.desktop.transition_inspector_transport import (
    DesktopTransitionInspectorError,
    DesktopTransitionInspectorTransport,
)

MAX_TRANSITION_INSPECTION_REQUEST_BYTES = 8 * 1024
_INSTALLED = False
_PATH = "/v1/playlist/transition/inspect"
_CONFLICT_CODES = {
    "transition_inspection_revision_not_found",
    "transition_inspection_snapshot_missing",
    "transition_inspection_identity_mismatch",
}


def install_transition_inspector_sidecar() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    original_handler = sidecar._SidecarRequestHandler
    original_server = sidecar._SidecarHTTPServer

    class TransitionInspectorRequestHandler(original_handler):
        def do_POST(self) -> None:  # noqa: N802
            if self.path != _PATH:
                super().do_POST()
                return
            if not self._authorized():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            payload = self._read_json_payload(MAX_TRANSITION_INSPECTION_REQUEST_BYTES)
            if payload is None or set(payload) != {"revision_id", "pair_index"}:
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid_transition_inspection_request"},
                )
                return
            try:
                result = self.sidecar_server.transition_inspector.inspect(
                    revision_id=payload["revision_id"],
                    pair_index=payload["pair_index"],
                )
            except DesktopTransitionInspectorError as exc:
                status = HTTPStatus.CONFLICT if exc.code in _CONFLICT_CODES else HTTPStatus.BAD_REQUEST
                self._write_json(status, {"error": exc.code})
                return
            except Exception:
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "transition_inspection_operation_failed"},
                )
                return
            self._write_json(HTTPStatus.OK, result)

    sidecar._SidecarRequestHandler = TransitionInspectorRequestHandler

    class TransitionInspectorHTTPServer(original_server):
        def __init__(self, startup: sidecar.SidecarStartup) -> None:
            super().__init__(startup)
            self.transition_inspector = DesktopTransitionInspectorTransport()

    sidecar._SidecarHTTPServer = TransitionInspectorHTTPServer
    _INSTALLED = True


__all__ = ["MAX_TRANSITION_INSPECTION_REQUEST_BYTES", "install_transition_inspector_sidecar"]
