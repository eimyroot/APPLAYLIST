from __future__ import annotations

from core.analysis.canonical_legacy_comparison import (
    FieldComparisonStatus,
    compare_canonical_to_legacy,
    normalize_key,
)
from data.models.analysis_record import AnalysisRecord
from data.models.canonical_analysis_record import (
    CanonicalAnalysisPersistenceRecord,
)


def _legacy(**overrides: object) -> AnalysisRecord:
    values: dict[str, object] = {
        "track_id": "track-1",
        "analysis_version": "0.1.0",
        "features_version": "0.1.0",
        "extractor_backend": "librosa",
        "extractor_name": "baseline",
        "bpm": 120.0,
        "bpm_confidence": 0.8,
        "key": "A",
        "scale": "minor",
        "camelot": "8A",
        "energy": 0.5,
        "loudness_db": -12.0,
        "duration_seconds": 180.0,
    }
    values.update(overrides)
    return AnalysisRecord(**values)


def _canonical(
    **overrides: object,
) -> CanonicalAnalysisPersistenceRecord:
    values: dict[str, object] = {
        "track_id": "track-1",
        "provider": "baseline",
        "provider_version": "1",
        "canonical_analysis_version": "canonical-mir-v1",
        "source_analysis_version": "0.1.0",
        "bpm": 120.5,
        "bpm_confidence": 0.82,
        "key": "A minor",
        "key_confidence": 0.7,
        "key_system": "standard",
        "energy": 0.52,
        "energy_confidence": 0.7,
        "loudness_db": -12.2,
        "loudness_integrated_lufs": None,
        "duration_seconds": 180.02,
        "sample_rate_hz": 44100,
        "channels": 2,
        "genre_hint": None,
        "analysis_status": "complete",
        "analyzed_at": None,
        "warnings_json": "[]",
    }
    values.update(overrides)
    return CanonicalAnalysisPersistenceRecord(**values)


def test_key_normalization_supports_camelot_and_minor_suffix() -> None:
    assert normalize_key(None, camelot="8A") == "A minor"
    assert normalize_key("Am") == "A minor"
    assert normalize_key("A minor") == "A minor"


def test_comparison_classifies_values_within_tolerance() -> None:
    result = compare_canonical_to_legacy(_legacy(), _canonical())

    assert result.outcome == "succeeded"
    statuses = {field.field: field.status for field in result.fields}
    assert statuses["bpm"] is FieldComparisonStatus.WITHIN_TOLERANCE
    assert statuses["key"] is FieldComparisonStatus.EXACT_MATCH
    assert statuses["energy"] is FieldComparisonStatus.WITHIN_TOLERANCE


def test_comparison_classifies_mismatch_and_missing_value() -> None:
    result = compare_canonical_to_legacy(
        _legacy(energy=None),
        _canonical(bpm=126.0, energy=0.7),
    )

    assert result.outcome == "mismatch"
    assert "bpm" in result.mismatched_fields
    assert "energy" in result.mismatched_fields


def test_comparison_rejects_different_track_identity() -> None:
    try:
        compare_canonical_to_legacy(
            _legacy(track_id="legacy"),
            _canonical(track_id="canonical"),
        )
    except ValueError as exc:
        assert "track_id" in str(exc)
    else:
        raise AssertionError("expected track identity mismatch")
