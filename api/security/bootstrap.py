from __future__ import annotations

from api.middleware.cors import install_cors
from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.request_size_guard import RequestSizeGuardMiddleware
from api.middleware.security_headers import SecurityHeadersMiddleware
from api.security.settings import SecuritySettings, settings


def apply_security_hardening(
    app,
    security_settings: SecuritySettings | None = None,
) -> None:
    config = security_settings or settings
    existing = getattr(app, "user_middleware", [])
    names = {mw.cls.__name__ for mw in existing if getattr(mw, "cls", None)}

    if "CORSMiddleware" not in names:
        install_cors(app, config)

    if config.enable_security_headers and "SecurityHeadersMiddleware" not in names:
        app.add_middleware(SecurityHeadersMiddleware)

    if config.enable_request_size_guard and "RequestSizeGuardMiddleware" not in names:
        app.add_middleware(
            RequestSizeGuardMiddleware,
            max_bytes=config.max_request_bytes,
        )

    if config.enable_rate_limit and "RateLimitMiddleware" not in names:
        app.add_middleware(
            RateLimitMiddleware,
            limit_per_minute=config.rate_limit_per_minute,
        )
