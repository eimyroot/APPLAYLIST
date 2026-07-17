from __future__ import annotations

from hmac import compare_digest

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.desktop.protocol import PROCESS_NONCE_HEADER, SESSION_HEADER, SidecarSession


PUBLIC_SIDECAR_PATHS = frozenset({"/health"})


class SidecarSessionAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, session: SidecarSession) -> None:
        super().__init__(app)
        self._session = session

    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_SIDECAR_PATHS:
            return await call_next(request)

        supplied_credential = request.headers.get(SESSION_HEADER)
        supplied_nonce = request.headers.get(PROCESS_NONCE_HEADER)
        if (
            supplied_credential is None
            or supplied_nonce is None
            or not compare_digest(supplied_credential, self._session.credential)
            or not compare_digest(supplied_nonce, self._session.process_nonce)
        ):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "type": "sidecar_unauthorized",
                        "message": "Missing or invalid desktop sidecar session",
                        "status_code": 401,
                    }
                },
            )

        return await call_next(request)
