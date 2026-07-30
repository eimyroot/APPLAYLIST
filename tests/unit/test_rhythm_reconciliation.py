from __future__ import annotations

import pytest

from core.analysis.provider_contracts import ProviderMetadata
from core.analysis.rhythm_contracts import (
    BeatEvent,
    BeatGrid,
    EvidenceProvenance,
    EvidenceStatus,
    SourceAudioIdentity,
)
from core.analysis.rhythm_reconciliation import (
    WB006C_SHADOW_ALGORITHM_VERSION,
    WB006C_SHADOW_METHOD,
    WB006C_SHADOW_PROVIDER,
    CanonicalTempoEvidence,
    TempoRelationship,
    reconcile_shadow_beat_grid,
)
from data.models.analysis_record import AnalysisRecord


def source_identity(*, digest: str = "a" * 64) -> SourceAudioIdentity:
    return SourceAudioIdentity(
        resolved_path="/tmp/applaylist-track.wav",
        sha256=digest,
        size_bytes=1024,
    )


def canonical(*, bpm: float | None = 120.0) -> CanonicalTempoEvidence:
    return CanonicalTempoEvidence(
        track_id="track",
        provider="baseline",
        provider_version="0.1.0",
        algorithm_version="bundle-4-audio-analyzer",
        source_analysis_version="0.1.0",
        source_identity=source_identity(),
        duration_seconds=60.0,
        bpm=bpm,
        bpm_confidence=None,
    )


def grid(
    *,
    bpm: float | None,
    provider: str = WB006C_SHADOW_PROVIDER,
    provider_version: str = "0.10.2.post1",
    algorithm_version: str = WB006C_SHADOW_ALGORITHM_VERSION,
    source_analysis_version: str = "0.1.0",
    identity: SourceAudioIdentity | None = None,
) -> BeatGrid:
    provenance = EvidenceProvenance(
        provider=provider,
        provider_version=provider_version,
        algorithm_version=algorithm_version,
        method=WB006C_SHADOW_METHOD,
        source_analysis_version=source_analysis_version,
        source_identity=identity or source_identity(),
    )
    if bpm is None:
        return BeatGrid(
            status=EvidenceStatus.UNAVAILABLE,
            beats=(),
            provenance=provenance,
            unavailable_reason="NO_BEATS",
        )
    return BeatGrid(
        status=EvidenceStatus.DERIVED,
        beats=(
            BeatEvent(index=0, time_seconds=0.5, confidence=0.8),
            BeatEvent(index=1, time_seconds=1.0, confidence=0.8),
        ),
        provenance=provenance,
        tempo_bpm=bpm,
        tempo_confidence=0.75,
    )


def test_analysis_record_adapter_preserves_missing_confidence_and_source_identity() -> None:
    record = AnalysisRecord(
        track_id="track",
        analysis_version="0.1.0",
        features_version="0.1.0",
        extractor_backend="librosa",
        extractor_name="bundle-4-audio-analyzer",
        bpm=120.0,
        bpm_confidence=None,
        duration_seconds=60.0,
    )
    metadata = ProviderMetadata(
        name="baseline",
        version="0.1.0",
        backend="audio-analyzer",
        capabilities=("bpm",),
    )
    identity = source_identity()
    evidence = CanonicalTempoEvidence.from_analysis_record(
        record,
        provider_metadata=metadata,
        source_identity=identity,
    )
    assert evidence.bpm == 120.0
    assert evidence.bpm_confidence is None
    assert evidence.algorithm_version == "bundle-4-audio-analyzer"
    assert evidence.source_identity == identity


@pytest.mark.parametrize(
    ("shadow_bpm", "relationship"),
    [
        (121.0, TempoRelationship.DIRECT),
        (60.0, TempoRelationship.HALF_TIME),
        (240.0, TempoRelationship.DOUBLE_TIME),
        (93.0, TempoRelationship.DIVERGENT),
    ],
)
def test_reconciliation_classifies_relationships(
    shadow_bpm: float,
    relationship: TempoRelationship,
) -> None:
    result = reconcile_shadow_beat_grid(canonical(), grid(bpm=shadow_bpm))
    assert result.relationship is relationship
    assert result.within_tolerance is (relationship is not TempoRelationship.DIVERGENT)
    assert result.canonical_provider == "baseline"
    assert result.shadow_provider == WB006C_SHADOW_PROVIDER


def test_reconciliation_preserves_unknown_for_missing_evidence() -> None:
    result = reconcile_shadow_beat_grid(canonical(bpm=None), grid(bpm=120.0))
    assert result.relationship is TempoRelationship.UNKNOWN
    assert result.within_tolerance is False


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"provider": "other-shadow"}, "provider identity"),
        ({"provider_version": "0.11.0"}, "provider version"),
        ({"algorithm_version": "other-algorithm"}, "algorithm identity"),
        ({"source_analysis_version": "different"}, "source analysis version"),
        ({"identity": source_identity(digest="b" * 64)}, "source identity"),
    ],
)
def test_reconciliation_rejects_provenance_mismatch(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        reconcile_shadow_beat_grid(canonical(), grid(bpm=120.0, **overrides))
