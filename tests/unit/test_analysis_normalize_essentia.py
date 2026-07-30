from core.analysis.contracts import CanonicalAnalysisResult
from core.analysis.normalize import normalize_provider_result


def test_normalize_essentia_payload_maps_values_without_fabricating_confidence():
    payload = {
        "source_path": "/music/b.mp3",
        "rhythm_bpm": 129.4,
        "key_key": "A minor",
        "key_strength": 0.88,
        "loudness_energy": 0.72,
        "loudness_integrated_lufs": -9.2,
        "sample_rate_hz": 44100,
        "duration_seconds": 302.1,
    }
    result = normalize_provider_result("essentia", payload)

    assert isinstance(result, CanonicalAnalysisResult)
    assert result.__class__.__module__ == "core.analysis.contracts"
    assert result.path == "/music/b.mp3"
    assert result.provider == "essentia"
    assert result.bpm == 129.4
    assert result.bpm_confidence is None
    assert result.key == "8A"
    assert result.key_confidence is None
    assert result.energy == 0.72
    assert result.energy_confidence is None
    assert result.loudness_integrated_lufs == -9.2
    assert result.provider_version is None
    assert result.analyzed_at is None
    assert result.raw_provider_fields["key_strength"] == 0.88


def test_normalize_librosa_missing_confidence_remains_none():
    result = normalize_provider_result(
        "librosa",
        {
            "source_path": "/music/a.wav",
            "tempo": 128.0,
            "energy": 0.5,
        },
    )

    assert result.bpm == 128.0
    assert result.bpm_confidence is None
    assert result.energy == 0.5
    assert result.energy_confidence is None


def test_normalize_preserves_explicit_confidence_and_provenance():
    result = normalize_provider_result(
        "essentia",
        {
            "source_path": "/music/c.wav",
            "rhythm_bpm": 127.0,
            "bpm_confidence": 0.61,
            "key": "8A",
            "key_confidence": 0.72,
            "energy": 0.44,
            "energy_confidence": 0.63,
            "provider_version": "2.1.0",
            "analysis_version": "provider-analysis-v3",
            "analyzed_at": "2026-07-30T10:00:00+00:00",
        },
    )

    assert result.bpm_confidence == 0.61
    assert result.key_confidence == 0.72
    assert result.energy_confidence == 0.63
    assert result.provider_version == "2.1.0"
    assert result.source_analysis_version == "provider-analysis-v3"
    assert result.analyzed_at == "2026-07-30T10:00:00+00:00"
