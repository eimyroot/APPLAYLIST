from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from core.analysis.canonical_writer_feature_flags import (
    canonical_writer_enabled,
)

_ALLOWED_NONLIVE_ENVS = {"development", "test", "staging", "nonlive"}
_PRODUCTION_ENVS = {"prod", "production"}


@dataclass(frozen=True)
class CanonicalWriterRuntimeProfile:
    enabled: bool
    app_env: str
    receipts_path: Path | None
    reason: str


def resolve_canonical_writer_runtime_profile(
    env: Mapping[str, str] | None = None,
) -> CanonicalWriterRuntimeProfile:
    source = {} if env is None else env
    app_env = source.get("APP_ENV", "development").strip().lower()
    requested = canonical_writer_enabled(source)
    raw_receipts_path = source.get(
        "APPLAYLIST_CANONICAL_WRITER_RECEIPTS_PATH",
        "",
    ).strip()

    if app_env in _PRODUCTION_ENVS:
        return CanonicalWriterRuntimeProfile(
            enabled=False,
            app_env=app_env,
            receipts_path=None,
            reason="production_fail_closed",
        )

    if not requested:
        return CanonicalWriterRuntimeProfile(
            enabled=False,
            app_env=app_env,
            receipts_path=None,
            reason="writer_not_requested",
        )

    if app_env not in _ALLOWED_NONLIVE_ENVS:
        return CanonicalWriterRuntimeProfile(
            enabled=False,
            app_env=app_env,
            receipts_path=None,
            reason="environment_not_allowlisted",
        )

    if not raw_receipts_path:
        return CanonicalWriterRuntimeProfile(
            enabled=False,
            app_env=app_env,
            receipts_path=None,
            reason="receipts_path_required",
        )

    return CanonicalWriterRuntimeProfile(
        enabled=True,
        app_env=app_env,
        receipts_path=Path(raw_receipts_path).expanduser(),
        reason="bounded_nonlive_enabled",
    )
