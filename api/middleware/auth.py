from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from core.security.auth import get_anonymous_context


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.auth = get_anonymous_context()
        response = await call_next(request)
        return response
