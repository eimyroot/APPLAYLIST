from core.composer.intelligence_hook import intelligence_contribution


def test_intelligence_affects_score():
    t_low = {
        "intelligence": {
            "club_readiness_score": 0.3,
            "mixability_score": 0.3
        }
    }

    t_high = {
        "intelligence": {
            "club_readiness_score": 0.9,
            "mixability_score": 0.8
        }
    }

    s1, _ = intelligence_contribution(t_low)
    s2, _ = intelligence_contribution(t_high)

    assert s2 > s1
