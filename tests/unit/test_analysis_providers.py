from __future__ import annotations

import pytest

from core.analysis.providers import (
    EssentiaAnalyzerProvider,
    LibrosaAnalyzerProvider,
    list_analyzer_providers,
    select_best_provider,
)


def test_list_analyzer_providers_has_expected_keys():
    infos = list_analyzer_providers()
    assert "librosa" in infos
    assert "essentia" in infos


def test_essentia_disabled_without_flag(monkeypatch):
    monkeypatch.delenv("APPLAYLIST_ENABLE_ESSENTIA", raising=False)
    info = EssentiaAnalyzerProvider.is_available()
    assert info.available is False
    assert "disabled by env" in info.reason


def test_select_unknown_provider_raises():
    with pytest.raises(ValueError):
        select_best_provider("nope")


def test_select_best_provider_prefers_librosa_if_available():
    info = LibrosaAnalyzerProvider.is_available()
    if info.available:
        provider = select_best_provider()
        assert provider.name == "librosa"
    else:
        pytest.skip("librosa not installed in this environment")
