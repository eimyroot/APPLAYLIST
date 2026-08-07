from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from typing import Protocol

from core.analysis.canonical_legacy_comparison import compare_canonical_to_legacy
from core.analysis.canonical_shadow_read_receipts import (
    CanonicalShadowReadReceipt,
    CanonicalShadowReadReceiptSink,
    JsonlCanonicalShadowReadReceiptSink,
)
from core.analysis.canonical_shadow_reader_profile import (
    resolve_canonical_shadow_reader_profile,
)
from data.models.analysis_record import AnalysisRecord
from data.models.canonical_analysis_record import (
    CanonicalAnalysisPersistenceRecord,
)
from data.repositories.canonical_analysis_repository import (
    CanonicalAnalysisRepository,
)

logger = logging.getLogger(__name__)


class CanonicalAnalysisReader(Protocol):
    def get(
        self,
        track_id: str,
    ) -> CanonicalAnalysisPersistenceRecord | None:
        ...


class CanonicalShadowReader:
    """Default-off observer that never replaces the authoritative legacy result."""

    def __init__(
        self,
        *,
        canonical_reader: CanonicalAnalysisReader | None = None,
        enabled: bool = False,
        receipt_sink: CanonicalShadowReadReceiptSink | None = None,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        if enabled and canonical_reader is None:
            raise ValueError(
                "canonical_reader is required when shadow reader is enabled"
            )
        if enabled and receipt_sink is None:
            raise ValueError(
                "receipt_sink is required when shadow reader is enabled"
            )
        self._canonical_reader = canonical_reader
        self._enabled = enabled
        self._receipt_sink = receipt_sink
        self._monotonic_ns = monotonic_ns

    @property
    def enabled(self) -> bool:
        return self._enabled

    def observe_authoritative_legacy_read(
        self,
        legacy: AnalysisRecord,
        *,
        correlation_id: str | None = None,
    ) -> AnalysisRecord:
        if not isinstance(legacy, AnalysisRecord):
            raise TypeError("legacy must be AnalysisRecord")
        if not self._enabled:
            return legacy

        reader = self._canonical_reader
        sink = self._receipt_sink
        if reader is None or sink is None:
            raise RuntimeError("enabled shadow reader dependency is missing")

        started_ns = self._monotonic_ns()
        try:
            canonical = reader.get(legacy.track_id)
            elapsed_ms = (self._monotonic_ns() - started_ns) / 1_000_000
            if canonical is None:
                receipt = CanonicalShadowReadReceipt.canonical_missing(
                    track_id=legacy.track_id,
                    legacy_analysis_version=legacy.analysis_version,
                    duration_ms=elapsed_ms,
                    correlation_id=correlation_id,
                )
            else:
                comparison = compare_canonical_to_legacy(legacy, canonical)
                receipt = CanonicalShadowReadReceipt.from_comparison(
                    comparison,
                    duration_ms=elapsed_ms,
                    correlation_id=correlation_id,
                )
        except Exception as exc:
            elapsed_ms = (self._monotonic_ns() - started_ns) / 1_000_000
            receipt = CanonicalShadowReadReceipt.failed(
                track_id=legacy.track_id,
                legacy_analysis_version=legacy.analysis_version,
                duration_ms=elapsed_ms,
                error_type=type(exc).__name__,
                correlation_id=correlation_id,
            )

        self._write_receipt(sink, receipt)
        self._log_receipt(receipt)
        return legacy

    @staticmethod
    def _write_receipt(
        sink: CanonicalShadowReadReceiptSink,
        receipt: CanonicalShadowReadReceipt,
    ) -> None:
        try:
            sink.write(receipt)
        except Exception as exc:
            logger.warning(
                "canonical_shadow_read_receipt_write_failed",
                extra={
                    "event_name": "canonical_shadow_read_receipt_write_failed",
                    "track_id": receipt.track_id,
                    "error_type": type(exc).__name__,
                },
            )

    @staticmethod
    def _log_receipt(receipt: CanonicalShadowReadReceipt) -> None:
        log = logger.warning if receipt.outcome == "failed" else logger.info
        log(
            receipt.event_name,
            extra={
                "event_name": receipt.event_name,
                "track_id": receipt.track_id,
                "provider": receipt.provider,
                "outcome": receipt.outcome,
                "mismatched_fields": receipt.mismatched_fields,
            },
        )


def create_canonical_shadow_reader(
    *,
    env: Mapping[str, str] | None = None,
    canonical_reader: CanonicalAnalysisReader | None = None,
    receipt_sink: CanonicalShadowReadReceiptSink | None = None,
) -> CanonicalShadowReader:
    profile = resolve_canonical_shadow_reader_profile(env)
    reader = canonical_reader
    sink = receipt_sink

    if profile.enabled:
        if reader is None:
            reader = CanonicalAnalysisRepository()
        if sink is None:
            if profile.receipts_path is None:
                raise RuntimeError(
                    "enabled shadow reader profile is missing receipts path"
                )
            sink = JsonlCanonicalShadowReadReceiptSink(
                profile.receipts_path
            )

    return CanonicalShadowReader(
        canonical_reader=reader,
        enabled=profile.enabled,
        receipt_sink=sink,
    )
