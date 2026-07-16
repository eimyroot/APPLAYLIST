from core.analysis.provider_registry import provider_capabilities, provider_registry


def test_provider_capabilities_contains_essentia():
    caps = provider_capabilities()
    assert "essentia" in caps
    assert "enabled" in caps["essentia"]
    assert "available" in caps["essentia"]
    assert "canonical_mapping_ready" in caps["essentia"]


def test_provider_registry_returns_dict():
    reg = provider_registry()
    assert isinstance(reg, dict)
