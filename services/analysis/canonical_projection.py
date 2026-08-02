from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from core.analysis.contracts import CanonicalAnalysisResult
from core.analysis.provider_contracts import ProviderMetadata
from data.models.analysis_record import AnalysisRecord


def project_analysis_record_to_canonical(
    record: AnalysisRecord,
    *,
    path: str | Path,
    provider_metadata: ProviderMetadata,
) -> CanonicalAnalysisResult:
    """Project an existing legacy AnalysisRecord into canonical read form.

    This is a read projection only. It does not imply that arbitrary canonical
    results can be persisted losslessly through the legacy analyses schema.
    """
    canonical_key = record.camelot or record.key
    return CanonicalAnalysisResult(
        path=str(path),
        provider=provider_metadata.name,
        bpm=record.bpm,
        bpm_confidence=record.bpm_confidence,
        key=canonical_key,
        key_system="camelot" if record.camelot else None,
        energy=record.energy,
        loudness_db=record.loudness_db,
        duration_seconds=record.duration_seconds,
        analysis_status="ok",
        source_analysis_version=record.analysis_version,
        provider_version=provider_metadata.version,
        track_id=record.track_id,
        raw_provider_fields=asdict(record),
    )
