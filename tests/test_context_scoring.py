from core.composer.intelligence_hook import intelligence_contribution


def test_default_context():
    t = {"intelligence": {"club_readiness_score": 1.0, "mixability_score": 1.0}}
    score, _ = intelligence_contribution(t)
    assert score > 0


def test_peak_vs_warmup():
    t = {"intelligence": {"club_readiness_score": 1.0, "mixability_score": 1.0}}

    s_peak, _ = intelligence_contribution(t, context="peak")
    s_warm, _ = intelligence_contribution(t, context="warmup")

    assert s_peak > s_warm
