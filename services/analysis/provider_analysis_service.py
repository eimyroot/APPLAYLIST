from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Protocol

from core.analysis.canonical_writer_feature_flags import (
    canonical_writer_enabled,
)
from core.analysis.provider_contracts import ProviderOutput
from core.analysis.provider_orchestrator import analyze_with_provider_selection
from data.models.canonical_analysis_record import (
    CanonicalAnalysisMappingError,
    CanonicalAnalysisPersistenceRecord,
    map_canonical_analysis_to_persistence,
)
from data.repositories.canonical_analysis_repository import (
    CanonicalAnalysisRepository,
    CanonicalAnalysisRepositoryError,
)

logger = logging.getLogger(__name__)


class CanonicalAnalysisWriter(Protocol):
    def upsert(self, record: CanonicalAnalysisPersistenceRecord) -> None:
        ...


class ProviderAnalysisService:
    """Optional provider analysis with a non-authoritative shadow writer."""

    def __init__(
        self,
        *,
        canonical_writer: CanonicalAnalysisWriter | None = None,
        canonical_writer_is_enabled: bool = False,
    ) -> None:
        if canonical_writer_is_enabled and canonical_writer is None:
            raise ValueError(
                "canonical_writer is required when canonical writer is enabled"
            )
        self._canonical_writer = canonical_writer
        self._canonical_writer_is_enabled = canonical_writer_is_enabled

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

        try:
            record = map_canonical_analysis_to_persistence(
                output.normalized,
            )
            writer.upsert(record)
        except (
            CanonicalAnalysisMappingError,
            CanonicalAnalysisRepositoryError,
        ) as exc:
            logger.warning(
                "canonical_writer_shadow_write_failed",
                extra={
                    "event_name": "canonical_writer_shadow_write_failed",
                    "provider": output.provider,
                    "track_id": output.normalized.track_id,
                    "error_type": type(exc).__name__,
                },
            )


def create_provider_analysis_service(
    *,
    env: Mapping[str, str] | None = None,
    canonical_writer: CanonicalAnalysisWriter | None = None,
) -> ProviderAnalysisService:
    enabled = canonical_writer_enabled(env)
    writer = canonical_writer

    if enabled and writer is None:
        writer = CanonicalAnalysisRepository()

    return ProviderAnalysisService(
        canonical_writer=writer,
        canonical_writer_is_enabled=enabled,
    )
