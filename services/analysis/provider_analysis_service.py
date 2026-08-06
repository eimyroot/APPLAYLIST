from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Protocol

from core.analysis.canonical_legacy_comparison import (
    COMPARISON_SCHEMA_VERSION,
    compare_canonical_to_legacy,
)
from core.analysis.canonical_legacy_comparison_profile import (
    resolve_canonical_legacy_comparison_profile,
)
from core.analysis.canonical_legacy_comparison_receipts import (
    CanonicalLegacyComparisonReceipt,
    CanonicalLegacyComparisonReceiptSink,
    JsonlCanonicalLegacyComparisonReceiptSink,
)
from core.analysis.canonical_writer_receipts import (
    CanonicalWriterReceipt,
    CanonicalWriterReceiptSink,
    JsonlCanonicalWriterReceiptSink,
)
from core.analysis.canonical_writer_runtime_profile import (
    resolve_canonical_writer_runtime_profile,
)
from core.analysis.provider_contracts import ProviderOutput
from core.analysis.provider_orchestrator import analyze_with_provider_selection
from data.models.analysis_record import AnalysisRecord
from data.models.canonical_analysis_record import (
    CanonicalAnalysisMappingError,
    CanonicalAnalysisPersistenceRecord,
    map_canonical_analysis_to_persistence,
)
from data.repositories.analysis_repository import AnalysisRepository
from data.repositories.canonical_analysis_repository import (
    CanonicalAnalysisRepository,
    CanonicalAnalysisRepositoryError,
)

logger = logging.getLogger(__name__)


class CanonicalAnalysisWriter(Protocol):
    def upsert(self, record: CanonicalAnalysisPersistenceRecord) -> None:
        ...


class LegacyAnalysisReader(Protocol):
    def get_by_track_id(self, track_id: str) -> AnalysisRecord | None:
        ...


class ProviderAnalysisService:
    """Provider analysis with optional non-authoritative evidence paths."""

    def __init__(
        self,
        *,
        canonical_writer: CanonicalAnalysisWriter | None = None,
        canonical_writer_is_enabled: bool = False,
        receipt_sink: CanonicalWriterReceiptSink | None = None,
        comparison_is_enabled: bool = False,
        legacy_analysis_reader: LegacyAnalysisReader | None = None,
        comparison_receipt_sink: (
            CanonicalLegacyComparisonReceiptSink | None
        ) = None,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        if canonical_writer_is_enabled and canonical_writer is None:
            raise ValueError(
                "canonical_writer is required when canonical writer is enabled"
            )
        if canonical_writer_is_enabled and receipt_sink is None:
            raise ValueError(
                "receipt_sink is required when canonical writer is enabled"
            )
        if comparison_is_enabled and not canonical_writer_is_enabled:
            raise ValueError(
                "comparison requires the canonical writer to be enabled"
            )
        if comparison_is_enabled and legacy_analysis_reader is None:
            raise ValueError(
                "legacy_analysis_reader is required when comparison is enabled"
            )
        if comparison_is_enabled and comparison_receipt_sink is None:
            raise ValueError(
                "comparison_receipt_sink is required when comparison is enabled"
            )
        self._canonical_writer = canonical_writer
        self._canonical_writer_is_enabled = canonical_writer_is_enabled
        self._receipt_sink = receipt_sink
        self._comparison_is_enabled = comparison_is_enabled
        self._legacy_analysis_reader = legacy_analysis_reader
        self._comparison_receipt_sink = comparison_receipt_sink
        self._monotonic_ns = monotonic_ns

    def analyze(
        self,
        *,
        track_id: str,
        path: str | Path,
        requested_provider: str | None = None,
        configured_default: str | None = None,
        safe_baseline: str = "baseline",
        provider_names: Iterable[str] | None = None,
    ) -> ProviderOutput:
        output = analyze_with_provider_selection(
            track_id=track_id,
            path=path,
            requested_provider=requested_provider,
            configured_default=configured_default,
            safe_baseline=safe_baseline,
            provider_names=provider_names,
        )

        if self._canonical_writer_is_enabled:
            self._write_canonical_result(output)

        return output

    def _write_canonical_result(self, output: ProviderOutput) -> None:
        writer = self._canonical_writer
        if writer is None:
            raise RuntimeError("enabled canonical writer dependency is missing")

        started_ns = self._monotonic_ns()
        try:
            record = map_canonical_analysis_to_persistence(output.normalized)
            writer.upsert(record)
        except (
            CanonicalAnalysisMappingError,
            CanonicalAnalysisRepositoryError,
        ) as exc:
            self._emit_receipt(output, started_ns, "failed", type(exc).__name__)
            logger.warning(
                "canonical_writer_shadow_write_failed",
                extra={
                    "event_name": "canonical_writer_shadow_write_failed",
                    "provider": output.provider,
                    "track_id": output.normalized.track_id,
                    "error_type": type(exc).__name__,
                },
            )
        else:
            self._emit_receipt(output, started_ns, "succeeded", None)
            logger.info(
                "canonical_writer_shadow_write_succeeded",
                extra={
                    "event_name": "canonical_writer_shadow_write_succeeded",
                    "provider": output.provider,
                    "track_id": output.normalized.track_id,
                    "canonical_analysis_version": (
                        output.normalized.analysis_version
                    ),
                },
            )
            if self._comparison_is_enabled:
                self._compare_with_legacy(record)

    def _compare_with_legacy(
        self,
        canonical: CanonicalAnalysisPersistenceRecord,
    ) -> None:
        reader = self._legacy_analysis_reader
        sink = self._comparison_receipt_sink
        if reader is None or sink is None:
            raise RuntimeError("enabled comparison dependency is missing")

        started_ns = self._monotonic_ns()
        try:
            legacy = reader.get_by_track_id(canonical.track_id)
            elapsed_ms = (self._monotonic_ns() - started_ns) / 1_000_000
            if legacy is None:
                receipt = CanonicalLegacyComparisonReceipt.skipped(
                    track_id=canonical.track_id,
                    provider=canonical.provider,
                    canonical_analysis_version=(
                        canonical.canonical_analysis_version
                    ),
                    comparison_schema_version=COMPARISON_SCHEMA_VERSION,
                    duration_ms=elapsed_ms,
                )
            else:
                comparison = compare_canonical_to_legacy(legacy, canonical)
                receipt = CanonicalLegacyComparisonReceipt.from_comparison(
                    comparison,
                    duration_ms=elapsed_ms,
                )
            self._write_comparison_receipt(sink, receipt)
            logger.info(
                receipt.event_name,
                extra={
                    "event_name": receipt.event_name,
                    "track_id": receipt.track_id,
                    "provider": receipt.provider,
                    "mismatched_fields": receipt.mismatched_fields,
                },
            )
        except Exception as exc:
            elapsed_ms = (self._monotonic_ns() - started_ns) / 1_000_000
            receipt = CanonicalLegacyComparisonReceipt.failed(
                track_id=canonical.track_id,
                provider=canonical.provider,
                canonical_analysis_version=(
                    canonical.canonical_analysis_version
                ),
                comparison_schema_version=COMPARISON_SCHEMA_VERSION,
                duration_ms=elapsed_ms,
                error_type=type(exc).__name__,
            )
            self._write_comparison_receipt(sink, receipt)
            logger.warning(
                "canonical_legacy_comparison_failed",
                extra={
                    "event_name": "canonical_legacy_comparison_failed",
                    "track_id": canonical.track_id,
                    "provider": canonical.provider,
                    "error_type": type(exc).__name__,
                },
            )

    @staticmethod
    def _write_comparison_receipt(
        sink: CanonicalLegacyComparisonReceiptSink,
        receipt: CanonicalLegacyComparisonReceipt,
    ) -> None:
        try:
            sink.write(receipt)
        except OSError as exc:
            logger.warning(
                "canonical_legacy_comparison_receipt_write_failed",
                extra={
                    "event_name": (
                        "canonical_legacy_comparison_receipt_write_failed"
                    ),
                    "track_id": receipt.track_id,
                    "provider": receipt.provider,
                    "error_type": type(exc).__name__,
                },
            )

    def _emit_receipt(
        self,
        output: ProviderOutput,
        started_ns: int,
        outcome: str,
        error_type: str | None,
    ) -> None:
        sink = self._receipt_sink
        if sink is None:
            return
        elapsed_ms = (self._monotonic_ns() - started_ns) / 1_000_000
        receipt = CanonicalWriterReceipt.create(
            outcome=outcome,
            duration_ms=elapsed_ms,
            provider=output.provider,
            canonical_analysis_version=output.normalized.analysis_version,
            track_id=output.normalized.track_id,
            error_type=error_type,
        )
        try:
            sink.write(receipt)
        except OSError as exc:
            logger.warning(
                "canonical_writer_receipt_write_failed",
                extra={
                    "event_name": "canonical_writer_receipt_write_failed",
                    "provider": output.provider,
                    "track_id": output.normalized.track_id,
                    "error_type": type(exc).__name__,
                },
            )


def create_provider_analysis_service(
    *,
    env: Mapping[str, str] | None = None,
    canonical_writer: CanonicalAnalysisWriter | None = None,
    receipt_sink: CanonicalWriterReceiptSink | None = None,
    legacy_analysis_reader: LegacyAnalysisReader | None = None,
    comparison_receipt_sink: (
        CanonicalLegacyComparisonReceiptSink | None
    ) = None,
) -> ProviderAnalysisService:
    writer_profile = resolve_canonical_writer_runtime_profile(env)
    comparison_profile = resolve_canonical_legacy_comparison_profile(
        writer_profile,
        env,
    )
    writer = canonical_writer
    writer_sink = receipt_sink
    reader = legacy_analysis_reader
    comparison_sink = comparison_receipt_sink

    if writer_profile.enabled:
        if writer is None:
            writer = CanonicalAnalysisRepository()
        if writer_sink is None:
            if writer_profile.receipts_path is None:
                raise RuntimeError("enabled profile is missing receipts path")
            writer_sink = JsonlCanonicalWriterReceiptSink(
                writer_profile.receipts_path
            )

    if comparison_profile.enabled:
        if reader is None:
            reader = AnalysisRepository()
        if comparison_sink is None:
            if comparison_profile.receipts_path is None:
                raise RuntimeError(
                    "enabled comparison is missing receipts path"
                )
            comparison_sink = JsonlCanonicalLegacyComparisonReceiptSink(
                comparison_profile.receipts_path
            )

    return ProviderAnalysisService(
        canonical_writer=writer,
        canonical_writer_is_enabled=writer_profile.enabled,
        receipt_sink=writer_sink,
        comparison_is_enabled=comparison_profile.enabled,
        legacy_analysis_reader=reader,
        comparison_receipt_sink=comparison_sink,
    )
