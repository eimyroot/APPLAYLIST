from __future__ import annotations

from core.analysis.canonical_writer_runtime_profile import (
    resolve_canonical_writer_runtime_profile,
)


def test_profile_defaults_off() -> None:
    profile = resolve_canonical_writer_runtime_profile({})
    assert profile.enabled is False
    assert profile.reason == "writer_not_requested"


def test_profile_requires_receipts_path() -> None:
    profile = resolve_canonical_writer_runtime_profile(
        {
            "APP_ENV": "staging",
            "APPLAYLIST_CANONICAL_WRITER_ENABLED": "1",
        }
    )
    assert profile.enabled is False
    assert profile.reason == "receipts_path_required"


def test_profile_enables_only_bounded_nonlive() -> None:
    profile = resolve_canonical_writer_runtime_profile(
        {
            "APP_ENV": "staging",
            "APPLAYLIST_CANONICAL_WRITER_ENABLED": "1",
            "APPLAYLIST_CANONICAL_WRITER_RECEIPTS_PATH": "./artifacts/receipts.jsonl",
        }
    )
    assert profile.enabled is True
    assert profile.reason == "bounded_nonlive_enabled"


def test_production_fails_closed_even_when_requested() -> None:
    profile = resolve_canonical_writer_runtime_profile(
        {
            "APP_ENV": "production",
            "APPLAYLIST_CANONICAL_WRITER_ENABLED": "1",
            "APPLAYLIST_CANONICAL_WRITER_RECEIPTS_PATH": "./receipts.jsonl",
        }
    )
    assert profile.enabled is False
    assert profile.reason == "production_fail_closed"
