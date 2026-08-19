from __future__ import annotations

from http import HTTPStatus

import services.desktop.sidecar as sidecar
from services.desktop.set_proposal_transport import (
    DesktopSetProposalTransport,
    DesktopSetProposalTransportError,
)

MAX_SET_PROPOSAL_REQUEST_BYTES = 64 * 1024
_SET_PROPOSAL_ROUTE = "/v1/set/proposal/generate"
_INSTALLED = False


def install_set_proposal_sidecar() -> None:
    """Extend the packaged canonical sidecar with one authenticated proposal route."""
    global _INSTALLED
    if _INSTALLED:
        return

    original_handler = sidecar._SidecarRequestHandler
    original_server = sidecar._SidecarHTTPServer

    class SetProposalRequestHandler(original_handler):
        def do_POST(self) -> None:  # noqa: N802
            if self.path == _SET_PROPOSAL_ROUTE:
                self._handle_set_proposal_generate()
                return
            super().do_POST()

        def _handle_set_proposal_generate(self) -> None:
            if not self._authorized():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            payload = self._read_json_payload(MAX_SET_PROPOSAL_REQUEST_BYTES)
            if (
                payload is None
                or set(payload) != {"track_ids", "seed_track_id", "target_track_count"}
                or not isinstance(payload.get("track_ids"), list)
            ):
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid_set_proposal_request"},
                )
                return
            try:
                result = self.sidecar_server.set_proposal.generate(
                    track_ids=payload["track_ids"],  # type: ignore[arg-type]
                    seed_track_id=payload["seed_track_id"],  # type: ignore[arg-type]
                    target_track_count=payload["target_track_count"],  # type: ignore[arg-type]
                )
            except DesktopSetProposalTransportError as exc:
                status = (
                    HTTPStatus.CONFLICT
                    if exc.code
                    in {
                        "set_proposal_track_unavailable",
                        "set_proposal_analysis_missing",
                        "set_proposal_analysis_failed",
                        "set_proposal_analysis_incomplete",
                    }
                    else HTTPStatus.BAD_REQUEST
                )
                self._write_json(status, {"error": exc.code})
                return
            except Exception:
                self._write_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "set_proposal_generation_failed"},
                )
                return
            self._write_json(HTTPStatus.OK, result)

    sidecar._SidecarRequestHandler = SetProposalRequestHandler

    class SetProposalHTTPServer(original_server):
        def __init__(self, startup: sidecar.SidecarStartup) -> None:
            super().__init__(startup)
            self.set_proposal = DesktopSetProposalTransport()

    sidecar._SidecarHTTPServer = SetProposalHTTPServer
    _INSTALLED = True


__all__ = ["MAX_SET_PROPOSAL_REQUEST_BYTES", "install_set_proposal_sidecar"]
