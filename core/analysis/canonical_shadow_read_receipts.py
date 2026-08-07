from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from core.analysis.canonical_legacy_comparison import (
    COMPARISON_SCHEMA_VERSION,
    CanonicalLegacyComparison,
)

_MAX_CORRELATION_ID_LENGTH = 128


def _bounded_correlation_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized[:_MAX_CORRELATION_ID_LENGTH]


@dataclass(frozen=True, slots=True)
class CanonicalShadowReadReceipt:
    event_name: str
    attempt_id: str
    correlation_id: str | None
    outcome: str
    track_id: str
    provider: str | None
    legacy_analysis_version: str
    canonical_analysis_version: str | None
    comparison_schema_version: str
    matched_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    duration_ms: float
    error_type: str | None
    recorded_at: str

    @classmethod
    def from_comparison(
        cls,
        comparison: CanonicalLegacyComparison,
        *,
        duration_ms: float,
        correlation_id: str | None = None,
    ) -> CanonicalShadowReadReceipt:
        return cls(
            event_name=f"canonical_shadow_read_{comparison.outcome}",
            attempt_id=str(uuid4()),
            correlation_id=_bounded_correlation_id(correlation_id),
            outcome=comparison.outcome,
            track_id=comparison.track_id,
            provider=comparison.provider,
            legacy_analysis_version=comparison.legacy_analysis_version,
            canonical_analysis_version=comparison.canonical_analysis_version,
            comparison_schema_version=comparison.comparison_schema_version,
            matched_fields=comparison.matched_fields,
            mismatched_fields=comparison.mismatched_fields,
            duration_ms=round(max(0.0, duration_ms), 3),
            error_type=None,
            recorded_at=datetime.now(UTC).isoformat(),
        )

    @classmethod
    def canonical_missing(
        cls,
        *,
        track_id: str,
        legacy_analysis_version: str,
        duration_ms: float,
        correlation_id: str | None = None,
    ) -> CanonicalShadowReadReceipt:
        return cls(
            event_name="canonical_shadow_read_canonical_missing",
            attempt_id=str(uuid4()),
            correlation_id=_bounded_correlation_id(correlation_id),
            outcome="canonical_missing",
            track_id=track_id,
            provider=None,
            legacy_analysis_version=legacy_analysis_version,
            canonical_analysis_version=None,
            comparison_schema_version=COMPARISON_SCHEMA_VERSION,
            matched_fields=(),
            mismatched_fields=(),
            duration_ms=round(max(0.0, duration_ms), 3),
            error_type=None,
            recorded_at=datetime.now(UTC).isoformat(),
        )

    @classmethod
    def failed(
        cls,
        *,
        track_id: str,
        legacy_analysis_version: str,
        duration_ms: float,
        error_type: str,
        correlation_id: str | None = None,
    ) -> CanonicalShadowReadReceipt:
        return cls(
            event_name="canonical_shadow_read_failed",
            attempt_id=str(uuid4()),
            correlation_id=_bounded_correlation_id(correlation_id),
            outcome="failed",
            track_id=track_id,
            provider=None,
            legacy_analysis_version=legacy_analysis_version,
            canonical_analysis_version=None,
            comparison_schema_version=COMPARISON_SCHEMA_VERSION,
            matched_fields=(),
            mismatched_fields=(),
            duration_ms=round(max(0.0, duration_ms), 3),
            error_type=error_type,
            recorded_at=datetime.now(UTC).isoformat(),
        )


class CanonicalShadowReadReceiptSink(Protocol):
    def write(self, receipt: CanonicalShadowReadReceipt) -> None:
        ...


class JsonlCanonicalShadowReadReceiptSink:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser()

    def write(self, receipt: CanonicalShadowReadReceipt) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            asdict(receipt),
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"
        descriptor = os.open(
            self._path,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        try:
            os.write(descriptor, payload.encode("utf-8"))
        finally:
            os.close(descriptor)
