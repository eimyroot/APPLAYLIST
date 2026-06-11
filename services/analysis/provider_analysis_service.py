from __future__ import annotations

from pathlib import Path
from typing import Iterable

from core.analysis.provider_contracts import ProviderOutput
from core.analysis.provider_orchestrator import analyze_with_provider_selection


class ProviderAnalysisService:
    """Optional provider-based analysis service.

    This service is a sidecar path.
    It does not replace the existing AudioAnalyzer or API behavior yet.
    """

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
        return analyze_with_provider_selection(
            track_id=track_id,
            path=path,
            requested_provider=requested_provider,
            configured_default=configured_default,
            safe_baseline=safe_baseline,
            provider_names=provider_names,
        )


def create_provider_analysis_service() -> ProviderAnalysisService:
    return ProviderAnalysisService()
