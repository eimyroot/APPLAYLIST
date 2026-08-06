from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_ALLOWED_NONLIVE_ENVS = {"development", "test", "staging", "nonlive"}
_PRODUCTION_ENVS = {"prod", "production"}
_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}


@dataclass(frozen=True, slots=True)
class CanonicalShadowReaderProfile:
    enabled: bool
    app_env: str
    receipts_path: Path | None
    reason: str


def resolve_canonical_shadow_reader_profile(
    env: Mapping[str, str] | None = None,
) -> CanonicalShadowReaderProfile:
    source = {} if env is None else env
    app_env = source.get("APP_ENV", "development").strip().lower()
    requested = (
        source.get("APPLAYLIST_CANONICAL_SHADOW_READER_ENABLED", "0")
        .strip()
        .lower()
        in _TRUE_VALUES
    )
    raw_receipts_path = source.get(
        "APPLAYLIST_CANONICAL_SHADOW_READER_RECEIPTS_PATH",
        "",
    ).strip()

    if app_env in _PRODUCTION_ENVS:
        return CanonicalShadowReaderProfile(
            enabled=False,
            app_env=app_env,
            receipts_path=None,
            reason="production_fail_closed",
        )
    if not requested:
        return CanonicalShadowReaderProfile(
            enabled=False,
            app_env=app_env,
            receipts_path=None,
            reason="reader_not_requested",
        )
    if app_env not in _ALLOWED_NONLIVE_ENVS:
        return CanonicalShadowReaderProfile(
            enabled=False,
            app_env=app_env,
            receipts_path=None,
            reason="environment_not_allowlisted",
        )
    if not raw_receipts_path:
        return CanonicalShadowReaderProfile(
            enabled=False,
            app_env=app_env,
            receipts_path=None,
            reason="receipts_path_required",
        )

    return CanonicalShadowReaderProfile(
        enabled=True,
        app_env=app_env,
        receipts_path=Path(raw_receipts_path).expanduser(),
        reason="bounded_nonlive_shadow_reader_enabled",
    )
