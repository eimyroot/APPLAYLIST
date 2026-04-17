import uuid
import asyncio
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from api.security.security import check_rate_limit, check_auth, enforce_size_limit

class SecurityMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        client_ip = request.client.host if request.client else "unknown"

        # SECURITY CHECKS
        check_rate_limit(client_ip)
        check_auth(request)
        enforce_size_limit(request)

        try:
            timeout = int(request.app.state.request_timeout)
            response = await asyncio.wait_for(call_next(request), timeout=timeout)
        except asyncio.TimeoutError:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=504, content={"error": "Request timeout"})

        response.headers["X-Request-ID"] = request_id
        return response
