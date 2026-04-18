from core.config.scoring_config import load_scoring_config


def test_default_config():
    cfg = load_scoring_config()
    assert "club_readiness_weight" in cfg
    assert "mixability_weight" in cfg
