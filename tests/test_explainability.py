from types import SimpleNamespace

from services.explainability.reasons import explain_transition


def test_explain_transition_contains_reasons() -> None:
    a = SimpleNamespace(bpm=128.0, camelot="8A", energy=0.5)
    b = SimpleNamespace(bpm=130.0, camelot="8A", energy=0.72)

    out = explain_transition(a, b, position=0.6)

    assert "reasons" in out
    assert len(out["reasons"]) >= 2
    assert "target_energy" in out
