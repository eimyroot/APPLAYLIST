from __future__ import annotations

from core.analysis.provider_feature_flags import (
    provider_analysis_enabled,
    provider_analysis_mode,
)


def test_provider_analysis_is_disabled_by_default() -> None:
    assert provider_analysis_enabled({}) is False
    assert provider_analysis_mode({}) == "legacy"


def test_provider_analysis_can_be_enabled() -> None:
    for value in ("1", "true", "yes", "on", "enabled"):
        env = {"APPLAYLIST_PROVIDER_ANALYSIS_ENABLED": value}

        assert provider_analysis_enabled(env) is True
        assert provider_analysis_mode(env) == "provider"


def test_provider_analysis_can_be_disabled_explicitly() -> None:
    for value in ("0", "false", "no", "off", "disabled", ""):
        env = {"APPLAYLIST_PROVIDER_ANALYSIS_ENABLED": value}

        assert provider_analysis_enabled(env) is False
        assert provider_analysis_mode(env) == "legacy"


def test_invalid_flag_fails_closed_to_legacy() -> None:
    env = {"APPLAYLIST_PROVIDER_ANALYSIS_ENABLED": "maybe"}

    assert provider_analysis_enabled(env) is False
    assert provider_analysis_mode(env) == "legacy"
