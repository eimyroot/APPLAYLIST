from pathlib import Path

from core.analysis.canonical_shadow_reader_profile import (
    resolve_canonical_shadow_reader_profile,
)


def test_shadow_reader_is_disabled_by_default() -> None:
    profile = resolve_canonical_shadow_reader_profile()

    assert profile.enabled is False
    assert profile.receipts_path is None
    assert profile.reason == "reader_not_requested"


def test_shadow_reader_fails_closed_in_production(tmp_path: Path) -> None:
    profile = resolve_canonical_shadow_reader_profile(
        {
            "APP_ENV": "production",
            "APPLAYLIST_CANONICAL_SHADOW_READER_ENABLED": "1",
            "APPLAYLIST_CANONICAL_SHADOW_READER_RECEIPTS_PATH": str(
                tmp_path / "receipts.jsonl"
            ),
        }
    )

    assert profile.enabled is False
    assert profile.receipts_path is None
    assert profile.reason == "production_fail_closed"


def test_shadow_reader_requires_allowlisted_environment(tmp_path: Path) -> None:
    profile = resolve_canonical_shadow_reader_profile(
        {
            "APP_ENV": "qa",
            "APPLAYLIST_CANONICAL_SHADOW_READER_ENABLED": "1",
            "APPLAYLIST_CANONICAL_SHADOW_READER_RECEIPTS_PATH": str(
                tmp_path / "receipts.jsonl"
            ),
        }
    )

    assert profile.enabled is False
    assert profile.reason == "environment_not_allowlisted"


def test_shadow_reader_requires_receipts_path() -> None:
    profile = resolve_canonical_shadow_reader_profile(
        {
            "APP_ENV": "test",
            "APPLAYLIST_CANONICAL_SHADOW_READER_ENABLED": "true",
        }
    )

    assert profile.enabled is False
    assert profile.reason == "receipts_path_required"


def test_shadow_reader_can_be_enabled_only_for_bounded_nonlive_use(
    tmp_path: Path,
) -> None:
    path = tmp_path / "receipts.jsonl"
    profile = resolve_canonical_shadow_reader_profile(
        {
            "APP_ENV": "nonlive",
            "APPLAYLIST_CANONICAL_SHADOW_READER_ENABLED": "enabled",
            "APPLAYLIST_CANONICAL_SHADOW_READER_RECEIPTS_PATH": str(path),
        }
    )

    assert profile.enabled is True
    assert profile.receipts_path == path
    assert profile.reason == "bounded_nonlive_shadow_reader_enabled"
