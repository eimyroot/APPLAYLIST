from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def ensure_request_id(request: Request) -> str:
    existing = getattr(request.state, "request_id", None)
    if existing:
        return existing

    header_id = request.headers.get("X-Request-ID")
    request_id = header_id or str(uuid.uuid4())
    request.state.request_id = request_id
    return request_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = ensure_request_id(request)
        request.state.started_at = time.time()

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
