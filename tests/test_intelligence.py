from types import SimpleNamespace
from services.intelligence.fusion import fuse_signals


def test_fusion_basic():
    local = SimpleNamespace(bpm=128, energy=0.6)
    external = {
        "tempo": 128,
        "energy": 0.6,
        "popularity": 50,
        "danceability": 0.7,
    }

    score = fuse_signals(local, external)
    assert score > 1.0
