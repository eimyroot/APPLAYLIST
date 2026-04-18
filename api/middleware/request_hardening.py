from __future__ import annotations

import asyncio
import os
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.security.guards import check_auth, check_payload_size, check_rate_limit

class RequestHardeningMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        client_ip = request.client.host if request.client else "unknown"

        check_rate_limit(client_ip)
        check_auth(request)
        check_payload_size(request)

        timeout_sec = int(os.getenv("REQUEST_TIMEOUT_SEC", "30"))

        try:
            response = await asyncio.wait_for(call_next(request), timeout=timeout_sec)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=504,
                content={"detail": "Request timeout", "request_id": request_id},
            )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response
