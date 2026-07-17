from __future__ import annotations

import os
from dataclasses import dataclass, field


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class SecuritySettings:
    """Immutable security configuration captured from the current environment."""

    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", os.getenv("ENV", "development")))
    allowed_origins_raw: str = field(default_factory=lambda: os.getenv("ALLOW_ORIGINS", "*"))
    rate_limit_per_minute: int = field(
        default_factory=lambda: _as_int(os.getenv("RATE_LIMIT_PER_MINUTE"), 120)
    )
    max_request_bytes: int = field(
        default_factory=lambda: _as_int(os.getenv("MAX_REQUEST_BYTES"), 2 * 1024 * 1024)
    )
    trusted_proxy_depth: int = field(
        default_factory=lambda: _as_int(os.getenv("TRUSTED_PROXY_DEPTH"), 0)
    )
    enable_security_headers: bool = field(
        default_factory=lambda: _as_bool(os.getenv("ENABLE_SECURITY_HEADERS"), True)
    )
    enable_request_size_guard: bool = field(
        default_factory=lambda: _as_bool(os.getenv("ENABLE_REQUEST_SIZE_GUARD"), True)
    )
    enable_rate_limit: bool = field(
        default_factory=lambda: _as_bool(os.getenv("ENABLE_RATE_LIMIT"), True)
    )
    auth_enabled_raw: bool = field(
        default_factory=lambda: _as_bool(os.getenv("AUTH_ENABLED"), False)
    )
    api_key: str = field(default_factory=lambda: os.getenv("API_KEY", ""))
    api_key_header_name: str = field(
        default_factory=lambda: os.getenv("API_KEY_HEADER_NAME", "X-API-Key")
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"prod", "production"}

    @property
    def allowed_origins(self) -> list[str]:
        raw = self.allowed_origins_raw.strip()
        if not raw:
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]

    @property
    def auth_enabled(self) -> bool:
        # Production cannot opt out of authentication. A missing key is handled
        # by the middleware as a controlled 503 misconfiguration response.
        if self.is_production:
            return True
        return self.auth_enabled_raw


# Backward-compatible process snapshot. New application instances should receive
# a freshly constructed SecuritySettings object through create_app().
settings = SecuritySettings()
