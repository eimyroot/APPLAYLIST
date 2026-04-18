from core.composer.energy_context import resolve_energy_context


def test_low_energy():
    t = {"intelligence": {"energy_score": 0.2}}
    assert resolve_energy_context(t, 5, 10) == "warmup"


def test_mid_energy():
    t = {"intelligence": {"energy_score": 0.5}}
    assert resolve_energy_context(t, 5, 10) == "peak"


def test_high_energy():
    t = {"intelligence": {"energy_score": 0.9}}
    assert resolve_energy_context(t, 5, 10) == "peak"


def test_fallback():
    t = {}
    ctx = resolve_energy_context(t, 9, 10)
    assert ctx in ["warmup", "peak", "closing"]
