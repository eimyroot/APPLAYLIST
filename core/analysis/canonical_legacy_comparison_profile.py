from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from core.analysis.canonical_writer_runtime_profile import (
    CanonicalWriterRuntimeProfile,
)

_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}


@dataclass(frozen=True, slots=True)
class CanonicalLegacyComparisonProfile:
    enabled: bool
    receipts_path: Path | None
    reason: str


def resolve_canonical_legacy_comparison_profile(
    writer_profile: CanonicalWriterRuntimeProfile,
    env: Mapping[str, str] | None = None,
) -> CanonicalLegacyComparisonProfile:
    source = {} if env is None else env
    requested = (
        source.get(
            "APPLAYLIST_CANONICAL_COMPARISON_ENABLED",
            "0",
        )
        .strip()
        .lower()
        in _TRUE_VALUES
    )
    raw_path = source.get(
        "APPLAYLIST_CANONICAL_COMPARISON_RECEIPTS_PATH",
        "",
    ).strip()

    if not writer_profile.enabled:
        return CanonicalLegacyComparisonProfile(
            enabled=False,
            receipts_path=None,
            reason="writer_profile_not_enabled",
        )
    if not requested:
        return CanonicalLegacyComparisonProfile(
            enabled=False,
            receipts_path=None,
            reason="comparison_not_requested",
        )
    if not raw_path:
        return CanonicalLegacyComparisonProfile(
            enabled=False,
            receipts_path=None,
            reason="comparison_receipts_path_required",
        )
    return CanonicalLegacyComparisonProfile(
        enabled=True,
        receipts_path=Path(raw_path).expanduser(),
        reason="bounded_nonlive_comparison_enabled",
    )
