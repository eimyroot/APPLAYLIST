from __future__ import annotations

import json
from dataclasses import replace

import pytest

from core.analysis.contracts import CanonicalAnalysisResult
from data.models.canonical_analysis_record import (
    CanonicalAnalysisMappingError,
    map_canonical_analysis_to_persistence,
)


def _canonical_result() -> CanonicalAnalysisResult:
    return CanonicalAnalysisResult(
        path="/private/audio/track.wav",
        provider="essentia",
        bpm=128.0,
        bpm_confidence=None,
        key="Am",
        key_confidence=0.91,
        key_system="traditional",
        energy=0.72,
        energy_confidence=None,
        loudness_db=-9.5,
        loudness_integrated_lufs=-10.1,
        duration_seconds=245.5,
        sample_rate_hz=44100,
        channels=2,
        genre_hint="techno",
        analysis_status="complete",
        analysis_version="canonical-mir-v1",
        source_analysis_version="essentia-profile-v1",
        provider_version="2.1",
        analyzed_at="2026-08-01T20:00:00+00:00",
        track_id="track-1",
        warnings=("zeta", "alpha"),
        raw_provider_fields={"provider_only": 123},
    )


def test_mapper_preserves_every_supported_persistence_field() -> None:
    record = map_canonical_analysis_to_persistence(_canonical_result())

    assert record.track_id == "track-1"
    assert record.provider == "essentia"
    assert record.provider_version == "2.1"
    assert record.canonical_analysis_version == "canonical-mir-v1"
    assert record.source_analysis_version == "essentia-profile-v1"
    assert record.bpm == 128.0
    assert record.bpm_confidence is None
    assert record.key == "Am"
    assert record.key_confidence == 0.91
    assert record.key_system == "traditional"
    assert record.energy == 0.72
    assert record.energy_confidence is None
    assert record.loudness_db == -9.5
    assert record.loudness_integrated_lufs == -10.1
    assert record.duration_seconds == 245.5
    assert record.sample_rate_hz == 44100
    assert record.channels == 2
    assert record.genre_hint == "techno"
    assert record.analysis_status == "complete"
    assert record.analyzed_at == "2026-08-01T20:00:00+00:00"


def test_mapper_preserves_missing_confidence_as_none() -> None:
    record = map_canonical_analysis_to_persistence(_canonical_result())

    assert record.bpm_confidence is None
    assert record.energy_confidence is None


def test_warnings_json_is_deterministic_and_round_trips() -> None:
    first = map_canonical_analysis_to_persistence(_canonical_result())
    second = map_canonical_analysis_to_persistence(_canonical_result())

    assert first.warnings_json == second.warnings_json
    assert first.warnings_json == '["zeta","alpha"]'
    assert json.loads(first.warnings_json) == ["zeta", "alpha"]
    assert first.warnings() == ("zeta", "alpha")


def test_mapper_rejects_missing_track_id() -> None:
    result = replace(_canonical_result(), track_id=None)

    with pytest.raises(
        CanonicalAnalysisMappingError,
        match="track_id",
    ):
        map_canonical_analysis_to_persistence(result)


def test_mapper_rejects_untyped_payload() -> None:
    with pytest.raises(TypeError):
        map_canonical_analysis_to_persistence(  # type: ignore[arg-type]
            {"track_id": "wrong"}
        )
