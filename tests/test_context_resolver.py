from core.composer.context_resolver import resolve_context


def test_warmup():
    assert resolve_context(1, 10) == "warmup"


def test_peak():
    assert resolve_context(5, 10) == "peak"


def test_closing():
    assert resolve_context(9, 10) == "closing"
