from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

from services.composition.shadow import (
    CompositionShadowReport,
    CompositionShadowService,
    ShadowComparisonRequest,
)


class CompositionReportSink(Protocol):
    def emit(self, report: CompositionShadowReport) -> None: ...


class CompositionComparisonService(Protocol):
    def compare(self, request: ShadowComparisonRequest) -> CompositionShadowReport: ...


@dataclass(slots=True)
class LoggingCompositionReportSink:
    """Emit a compact comparison summary through the standard logging boundary."""

    logger: logging.Logger = field(
        default_factory=lambda: logging.getLogger("applaylist.composition.comparison")
    )

    def emit(self, report: CompositionShadowReport) -> None:
        self.logger.info(
            "composition comparison completed",
            extra={
                "canonical_status": report.canonical_status.value,
                "candidate_count": report.candidate_count,
                "adapted_count": report.adapted_count,
                "rejected_count": report.rejected_count,
                "fallback_count": report.fallback_count,
                "overlap_count": report.overlap_count,
                "position_match_count": report.position_match_count,
                "legacy_coverage_ratio": report.legacy_coverage_ratio,
                "canonical_coverage_ratio": report.canonical_coverage_ratio,
            },
        )


class PipelineCompositionComparisonHook:
    """Build and emit a read-only canonical comparison for one legacy run."""

    def __init__(
        self,
        *,
        service: CompositionComparisonService | None = None,
        sink: CompositionReportSink | None = None,
    ) -> None:
        self._service = service if service is not None else CompositionShadowService()
        self._sink = sink if sink is not None else LoggingCompositionReportSink()

    def observe(
        self,
        *,
        legacy_track_ids: tuple[str, ...],
        target_track_count: int,
        bpm_min: float | None,
        bpm_max: float | None,
        mode: str | None,
    ) -> CompositionShadowReport:
        report = self._service.compare(
            ShadowComparisonRequest(
                legacy_track_ids=legacy_track_ids,
                target_track_count=target_track_count,
                bpm_min=bpm_min if bpm_min is not None else 1.0,
                bpm_max=bpm_max if bpm_max is not None else 300.0,
                mode=mode if mode is not None else "club",
            )
        )
        self._sink.emit(report)
        return report
