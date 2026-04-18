from __future__ import annotations

from core.analysis.adapter import canonicalize_provider_result
from core.analysis.contracts import CanonicalMirAnalysis


def test_canonicalize_provider_result_from_nested_payload():
    payload = {
        "provider": "librosa",
        "status": "ok",
        "beat": {"bpm": 128.4, "confidence": 0.91},
        "key": {"camelot": "10A", "confidence": 0.88},
        "metrics": {"energy_score": 0.67, "loudness_db": -8.4},
        "tags": {"primary_genre_hint": "tech house"},
        "duration_seconds": 367.2,
    }

    result = canonicalize_provider_result(payload, path="/tmp/demo.mp3")

    assert isinstance(result, CanonicalMirAnalysis)
    assert result.path == "/tmp/demo.mp3"
    assert result.provider == "librosa"
    assert result.bpm == 128.4
    assert result.bpm_confidence == 0.91
    assert result.key == "10A"
    assert result.key_confidence == 0.88
    assert result.energy == 0.67
    assert result.loudness_db == -8.4
    assert result.duration_seconds == 367.2
    assert result.genre_hint == "tech house"
    assert result.analysis_status == "ok"


def test_canonicalize_provider_result_from_flat_payload():
    payload = {
        "provider": "essentia",
        "status": "ok",
        "bpm": "130.0",
        "bpm_confidence": "0.75",
        "key": "11A",
        "key_confidence": "0.81",
        "energy": "0.52",
        "loudness_db": "-9.1",
        "duration_sec": "301.5",
        "genre_hint": "minimal techno",
    }

    result = canonicalize_provider_result(payload, path="/tmp/demo2.mp3")

    assert result.provider == "essentia"
    assert result.bpm == 130.0
    assert result.bpm_confidence == 0.75
    assert result.key == "11A"
    assert result.key_confidence == 0.81
    assert result.energy == 0.52
    assert result.loudness_db == -9.1
    assert result.duration_seconds == 301.5
    assert result.genre_hint == "minimal techno"
    assert result.analysis_status == "ok"


def test_canonical_contract_to_dict():
    payload = {
        "provider": "librosa",
        "status": "stub",
    }

    result = canonicalize_provider_result(payload, path="/tmp/empty.mp3")
    data = result.to_dict()

    assert data["path"] == "/tmp/empty.mp3"
    assert data["provider"] == "librosa"
    assert data["analysis_status"] == "stub"
    assert data["analysis_version"] == "canonical-mir-v1"
