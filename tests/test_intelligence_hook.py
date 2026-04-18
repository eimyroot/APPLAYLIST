from core.composer.intelligence_hook import intelligence_contribution


def test_no_intelligence():
    track = {}
    score, reasons = intelligence_contribution(track)

    assert score == 0
    assert reasons == []


def test_with_intelligence():
    track = {
        "intelligence": {
            "club_readiness_score": 0.8,
            "mixability_score": 0.6
        }
    }

    score, reasons = intelligence_contribution(track)

    assert score > 0
    assert len(reasons) == 2


def test_prefer_higher_intelligence():
    t1 = {
        "intelligence": {
            "club_readiness_score": 0.4,
            "mixability_score": 0.4
        }
    }

    t2 = {
        "intelligence": {
            "club_readiness_score": 0.9,
            "mixability_score": 0.8
        }
    }

    s1, _ = intelligence_contribution(t1)
    s2, _ = intelligence_contribution(t2)

    assert s2 > s1
