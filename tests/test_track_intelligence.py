from core.intelligence.track_intelligence import compute_intelligence


def test_intelligence_basic():
    track = {
        "bpm": 128,
        "energy": 0.8,
        "key": "10A"
    }

    result = compute_intelligence(track)

    assert "club_readiness_score" in result
    assert result["club_readiness_score"] > 0
    assert len(result["reasons"]) > 0
