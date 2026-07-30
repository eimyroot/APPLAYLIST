from __future__ import annotations

from dataclasses import asdict

from core.analysis.provider_contracts import (
    ProviderAvailability,
    ProviderInput,
    ProviderMetadata,
    ProviderOutput,
    available,
)
from core.analysis.provider_errors import provider_runtime_error

BASELINE_PROVIDER_METADATA = ProviderMetadata(
    name="baseline",
    version="0.1.0",
    backend="audio-analyzer",
    capabilities=(
        "bpm",
        "key",
        "camelot",
        "energy",
        "loudness",
    ),
    optional_dependencies=(),
)


class BaselineAnalysisProvider:
    """Stable baseline provider adapter.

    Important:
    AudioAnalyzer is imported lazily inside analyze(), not on module import.
    This keeps provider metadata and registry boot paths safe.
    """

    metadata = BASELINE_PROVIDER_METADATA

    def availability(self) -> ProviderAvailability:
        return available(self.metadata.name)

    def analyze(self, provider_input: ProviderInput) -> ProviderOutput:
        try:
            from services.analysis.analyzer import AudioAnalyzer
            from services.analysis.canonical_projection import (
                project_analysis_record_to_canonical,
            )

            record = AudioAnalyzer().analyze_file(
                track_id=provider_input.track_id,
                path=str(provider_input.path),
            )
        except Exception as exc:
            raise provider_runtime_error(
                self.metadata.name,
                f"Baseline analysis failed: {exc}",
            ) from exc

        normalized = project_analysis_record_to_canonical(
            record,
            path=provider_input.path,
            provider_metadata=self.metadata,
        )

        return ProviderOutput(
            provider=self.metadata.name,
            backend=self.metadata.backend,
            raw=asdict(record),
            normalized=normalized,
        )


def create_baseline_provider() -> BaselineAnalysisProvider:
    return BaselineAnalysisProvider()


def get_baseline_provider_metadata() -> ProviderMetadata:
    return BASELINE_PROVIDER_METADATA
