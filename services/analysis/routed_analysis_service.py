from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core.analysis.provider_feature_flags import provider_analysis_mode
from services.analysis.provider_analysis_service import (
    create_provider_analysis_service,
)


@dataclass(frozen=True)
class RoutedAnalysisResult:
    mode: str
    provider: str
    backend: str
    track_id: str
    payload: dict[str, Any]


class RoutedAnalysisService:
    """Feature-flagged router between legacy and provider analysis.

    Default behavior remains legacy. Provider mode is used only when
    APPLAYLIST_PROVIDER_ANALYSIS_ENABLED is explicitly enabled.
    """

    def analyze(
        self,
        *,
        track_id: str,
        path: str | Path,
        env: dict[str, str] | None = None,
        requested_provider: str | None = None,
        configured_default: str | None = None,
        safe_baseline: str = "baseline",
        provider_names: Iterable[str] | None = None,
    ) -> RoutedAnalysisResult:
        mode = provider_analysis_mode(env)

        if mode == "provider":
            output = create_provider_analysis_service().analyze(
                track_id=track_id,
                path=path,
                requested_provider=requested_provider,
                configured_default=configured_default,
                safe_baseline=safe_baseline,
                provider_names=provider_names,
            )
            return RoutedAnalysisResult(
                mode="provider",
                provider=output.provider,
                backend=output.backend,
                track_id=track_id,
                payload=output.normalized.to_dict(),
            )

        from services.analysis.analyzer import AudioAnalyzer

        record = AudioAnalyzer().analyze_file(
            track_id=track_id,
            path=str(path),
        )

        return RoutedAnalysisResult(
            mode="legacy",
            provider="legacy",
            backend=record.extractor_backend,
            track_id=track_id,
            payload=asdict(record),
        )


def create_routed_analysis_service() -> RoutedAnalysisService:
    return RoutedAnalysisService()
