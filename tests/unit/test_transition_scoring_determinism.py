from types import SimpleNamespace

from services.composer.scoring import score_transition


def test_legacy_score_is_deterministic_without_external_features() -> None:
    a = SimpleNamespace(track_id="a", bpm=128.0, camelot="8A", energy=0.5)
    b = SimpleNamespace(track_id="b", bpm=129.0, camelot="9A", energy=0.6)
    values = [score_transition(a, b) for _ in range(100)]
    assert len(set(values)) == 1


def test_external_features_are_explicit_and_deterministic() -> None:
    a = SimpleNamespace(track_id="a", bpm=128.0, camelot="8A", energy=0.5)
    b = SimpleNamespace(track_id="b", bpm=129.0, camelot="9A", energy=0.6)
    external = {
        "tempo": 129.0,
        "energy": 0.6,
        "popularity": 50,
        "danceability": 0.7,
    }
    assert score_transition(a, b, external_features=external) == score_transition(
        a,
        b,
        external_features=external,
    )


def test_incompatible_key_is_not_rejected() -> None:
    a = SimpleNamespace(track_id="a", bpm=128.0, camelot="8A", energy=0.5)
    b = SimpleNamespace(track_id="b", bpm=129.0, camelot="2B", energy=0.6)
    assert score_transition(a, b) >= 0.0
