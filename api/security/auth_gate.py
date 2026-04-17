from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from api.security.settings import settings


WRITE_PREFIXES = (
    "/jobs/",
    "/pipeline/run",
)
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.auth_enabled:
            return await call_next(request)

        if request.method in SAFE_METHODS:
            return await call_next(request)

        path = request.url.path
        if not any(path.startswith(prefix) for prefix in WRITE_PREFIXES):
            return await call_next(request)

        supplied = request.headers.get(settings.api_key_header_name)
        expected = settings.api_key

        if not expected:
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "type": "auth_misconfigured",
                        "message": "API auth is enabled but no API key is configured",
                        "status_code": 503,
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
            )

        if supplied != expected:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "type": "unauthorized",
                        "message": "Missing or invalid API key",
                        "status_code": 401,
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
            )

        return await call_next(request)
