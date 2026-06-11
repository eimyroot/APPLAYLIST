from core.analysis.normalize import normalize_provider_result


def test_normalize_essentia_payload_maps_to_camelot():
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

    assert result.source_path == "/music/b.mp3"
    assert result.tempo.bpm == 129.4
    assert result.tempo.confidence == 0.8
    assert result.key.value == "8A"
    assert result.key.confidence == 0.88
    assert result.energy.value == 0.72
    assert result.loudness_integrated_lufs == -9.2
    assert result.provenance.provider == "essentia"
