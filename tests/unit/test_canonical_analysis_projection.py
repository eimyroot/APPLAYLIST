from pathlib import Path

from core.analysis.provider_contracts import ProviderMetadata
from data.models.analysis_record import AnalysisRecord
from services.analysis.canonical_projection import project_analysis_record_to_canonical


def _record(*, camelot: str | None = "8A") -> AnalysisRecord:
    return AnalysisRecord(
        track_id="track-1",
        analysis_version="legacy-analysis-v1",
        features_version="legacy-features-v1",
        extractor_backend="librosa",
        extractor_name="bundle-4-audio-analyzer",
        bpm=128.0,
        bpm_confidence=None,
        key="A",
        scale="minor",
        camelot=camelot,
        energy=0.72,
        loudness_db=-9.5,
        duration_seconds=180.0,
        harmonic_ratio=0.4,
        percussive_ratio=0.6,
    )


def _metadata() -> ProviderMetadata:
    return ProviderMetadata(
        name="baseline",
        version="0.1.0",
        backend="audio-analyzer",
    )


def test_projection_preserves_explicit_legacy_evidence() -> None:
    record = _record()

    result = project_analysis_record_to_canonical(
        record,
        path=Path("/library/track.wav"),
        provider_metadata=_metadata(),
    )

    assert result.path == "/library/track.wav"
    assert result.provider == "baseline"
    assert result.provider_version == "0.1.0"
    assert result.track_id == "track-1"
    assert result.source_analysis_version == "legacy-analysis-v1"
    assert result.analysis_version == "canonical-mir-v1"
    assert result.bpm == 128.0
    assert result.bpm_confidence is None
    assert result.key == "8A"
    assert result.key_system == "camelot"
    assert result.energy == 0.72
    assert result.loudness_db == -9.5
    assert result.duration_seconds == 180.0
    assert result.analyzed_at is None
    assert result.raw_provider_fields["features_version"] == "legacy-features-v1"
    assert result.raw_provider_fields["extractor_backend"] == "librosa"
    assert result.raw_provider_fields["extractor_name"] == "bundle-4-audio-analyzer"
    assert result.raw_provider_fields["scale"] == "minor"
    assert result.raw_provider_fields["harmonic_ratio"] == 0.4
    assert result.raw_provider_fields["percussive_ratio"] == 0.6


def test_projection_does_not_invent_key_system_without_camelot() -> None:
    result = project_analysis_record_to_canonical(
        _record(camelot=None),
        path="/library/track.wav",
        provider_metadata=_metadata(),
    )

    assert result.key == "A"
    assert result.key_system is None
    assert result.key_confidence is None
    assert result.energy_confidence is None
    assert result.analyzed_at is None
