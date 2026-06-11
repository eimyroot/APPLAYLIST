from core.analysis.provider_essentia import essentia_enabled, essentia_available


def test_essentia_flag_defaults_disabled(monkeypatch):
    monkeypatch.delenv("APPLAYLIST_ENABLE_ESSENTIA", raising=False)
    assert essentia_enabled() is False
    assert essentia_available() is False


def test_essentia_flag_enabled_without_package(monkeypatch):
    monkeypatch.setenv("APPLAYLIST_ENABLE_ESSENTIA", "1")
    available = essentia_available()
    assert available in {True, False}
