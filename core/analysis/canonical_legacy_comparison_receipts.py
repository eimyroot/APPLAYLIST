from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from core.analysis.canonical_legacy_comparison import (
    CanonicalLegacyComparison,
)


@dataclass(frozen=True, slots=True)
class CanonicalLegacyComparisonReceipt:
    event_name: str
    attempt_id: str
    outcome: str
    track_id: str
    provider: str
    legacy_analysis_version: str | None
    canonical_analysis_version: str
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
    ) -> CanonicalLegacyComparisonReceipt:
        return cls(
            event_name=(
                f"canonical_legacy_comparison_{comparison.outcome}"
            ),
            attempt_id=str(uuid4()),
            outcome=comparison.outcome,
            track_id=comparison.track_id,
            provider=comparison.provider,
            legacy_analysis_version=comparison.legacy_analysis_version,
            canonical_analysis_version=(
                comparison.canonical_analysis_version
            ),
            comparison_schema_version=(
                comparison.comparison_schema_version
            ),
            matched_fields=comparison.matched_fields,
            mismatched_fields=comparison.mismatched_fields,
            duration_ms=round(max(0.0, duration_ms), 3),
            error_type=None,
            recorded_at=datetime.now(UTC).isoformat(),
        )

    @classmethod
    def skipped(
        cls,
        *,
        track_id: str,
        provider: str,
        canonical_analysis_version: str,
        comparison_schema_version: str,
        duration_ms: float,
    ) -> CanonicalLegacyComparisonReceipt:
        return cls(
            event_name="canonical_legacy_comparison_skipped",
            attempt_id=str(uuid4()),
            outcome="skipped",
            track_id=track_id,
            provider=provider,
            legacy_analysis_version=None,
            canonical_analysis_version=canonical_analysis_version,
            comparison_schema_version=comparison_schema_version,
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
        provider: str,
        canonical_analysis_version: str,
        comparison_schema_version: str,
        duration_ms: float,
        error_type: str,
    ) -> CanonicalLegacyComparisonReceipt:
        return cls(
            event_name="canonical_legacy_comparison_failed",
            attempt_id=str(uuid4()),
            outcome="failed",
            track_id=track_id,
            provider=provider,
            legacy_analysis_version=None,
            canonical_analysis_version=canonical_analysis_version,
            comparison_schema_version=comparison_schema_version,
            matched_fields=(),
            mismatched_fields=(),
            duration_ms=round(max(0.0, duration_ms), 3),
            error_type=error_type,
            recorded_at=datetime.now(UTC).isoformat(),
        )


class CanonicalLegacyComparisonReceiptSink(Protocol):
    def write(self, receipt: CanonicalLegacyComparisonReceipt) -> None:
        ...


class JsonlCanonicalLegacyComparisonReceiptSink:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser()

    def write(self, receipt: CanonicalLegacyComparisonReceipt) -> None:
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
