from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from services.composition.receipt import (
    CompositionComparisonReceipt,
    build_composition_comparison_receipt,
)
from services.composition.shadow import (
    CompositionShadowReport,
    CompositionShadowService,
    ShadowComparisonRequest,
)


class CompositionReceiptSink(Protocol):
    def emit(self, receipt: CompositionComparisonReceipt) -> None: ...


class CompositionComparisonService(Protocol):
    def compare(self, request: ShadowComparisonRequest) -> CompositionShadowReport: ...


@dataclass(slots=True)
class LoggingCompositionReceiptSink:
    """Emit a compact comparison receipt summary through the logging boundary."""

    logger: logging.Logger = field(
        default_factory=lambda: logging.getLogger("applaylist.composition.comparison")
    )

    def emit(self, receipt: CompositionComparisonReceipt) -> None:
        self.logger.info(
            "composition comparison completed",
            extra={
                "run_id": receipt.run_id,
                "receipt_schema_version": receipt.schema_version,
                "canonical_status": receipt.canonical_status,
                "candidate_count": receipt.candidate_count,
                "adapted_count": receipt.adapted_count,
                "rejected_count": receipt.rejected_count,
                "fallback_count": receipt.fallback_count,
                "overlap_count": receipt.overlap_count,
                "position_match_count": receipt.position_match_count,
                "legacy_coverage_ratio": receipt.legacy_coverage_ratio,
                "canonical_coverage_ratio": receipt.canonical_coverage_ratio,
            },
        )


class PipelineCompositionComparisonHook:
    """Build and emit a correlated read-only receipt for one legacy run."""

    def __init__(
        self,
        *,
        service: CompositionComparisonService | None = None,
        sink: CompositionReceiptSink | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._service = service if service is not None else CompositionShadowService()
        self._sink = sink if sink is not None else LoggingCompositionReceiptSink()
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    def observe(
        self,
        *,
        run_id: str,
        legacy_track_ids: tuple[str, ...],
        target_track_count: int,
        bpm_min: float | None,
        bpm_max: float | None,
        mode: str | None,
    ) -> CompositionComparisonReceipt:
        resolved_bpm_min = bpm_min if bpm_min is not None else 1.0
        resolved_bpm_max = bpm_max if bpm_max is not None else 300.0
        resolved_mode = mode if mode is not None else "club"
        report = self._service.compare(
            ShadowComparisonRequest(
                legacy_track_ids=legacy_track_ids,
                target_track_count=target_track_count,
                bpm_min=resolved_bpm_min,
                bpm_max=resolved_bpm_max,
                mode=resolved_mode,
            )
        )
        receipt = build_composition_comparison_receipt(
            run_id=run_id,
            generated_at=self._clock(),
            target_track_count=target_track_count,
            bpm_min=resolved_bpm_min,
            bpm_max=resolved_bpm_max,
            mode=resolved_mode,
            report=report,
        )
        self._sink.emit(receipt)
        return receipt
