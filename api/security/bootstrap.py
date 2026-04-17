from __future__ import annotations

from fastapi.middleware.cors import CORSMiddleware

from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.request_size_guard import RequestSizeGuardMiddleware
from api.middleware.security_headers import SecurityHeadersMiddleware
from api.security.settings import settings


def apply_security_hardening(app) -> None:
    existing = getattr(app, "user_middleware", [])

    names = {mw.cls.__name__ for mw in existing if getattr(mw, "cls", None)}

    if "CORSMiddleware" not in names:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if settings.enable_security_headers and "SecurityHeadersMiddleware" not in names:
        app.add_middleware(SecurityHeadersMiddleware)

    if settings.enable_request_size_guard and "RequestSizeGuardMiddleware" not in names:
        app.add_middleware(
            RequestSizeGuardMiddleware,
            max_bytes=settings.max_request_bytes,
        )

    if settings.enable_rate_limit and "RateLimitMiddleware" not in names:
        app.add_middleware(
            RateLimitMiddleware,
            limit_per_minute=settings.rate_limit_per_minute,
        )
