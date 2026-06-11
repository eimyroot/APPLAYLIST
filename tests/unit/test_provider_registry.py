from core.analysis.provider_registry import provider_capabilities, provider_registry


def test_provider_capabilities_contains_essentia():
    caps = provider_capabilities()
    assert "essentia" in caps
    assert "extracts" in caps["essentia"]
    assert "bpm" in caps["essentia"]["extracts"]


def test_provider_registry_returns_dict():
    reg = provider_registry()
    assert isinstance(reg, dict)
