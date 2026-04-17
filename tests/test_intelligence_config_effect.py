from core.composer.intelligence_hook import intelligence_contribution


def test_config_affects_score():
    t = {
        "intelligence": {
            "club_readiness_score": 1.0,
            "mixability_score": 1.0
        }
    }

    score, _ = intelligence_contribution(t)
    assert score > 0
