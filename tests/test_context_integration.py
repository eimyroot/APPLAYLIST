from core.composer.context_intelligence import contextual_score


def test_context_changes_score():
    t = {
        "intelligence": {
            "club_readiness_score": 1.0,
            "mixability_score": 1.0
        }
    }

    s1, _ = contextual_score(t, 1, 10)
    s2, _ = contextual_score(t, 9, 10)

    assert s1 != s2
