from __future__ import annotations

from core.analysis.canonical_legacy_comparison_profile import (
    resolve_canonical_legacy_comparison_profile,
)
from core.analysis.canonical_writer_runtime_profile import (
    resolve_canonical_writer_runtime_profile,
)


def test_comparison_requires_enabled_writer_profile() -> None:
    writer = resolve_canonical_writer_runtime_profile({})
    comparison = resolve_canonical_legacy_comparison_profile(
        writer,
        {
            "APPLAYLIST_CANONICAL_COMPARISON_ENABLED": "1",
            "APPLAYLIST_CANONICAL_COMPARISON_RECEIPTS_PATH": "receipt.jsonl",
        },
    )
    assert comparison.enabled is False
    assert comparison.reason == "writer_profile_not_enabled"


def test_comparison_requires_explicit_receipt_path() -> None:
    env = {
        "APP_ENV": "test",
        "APPLAYLIST_CANONICAL_WRITER_ENABLED": "1",
        "APPLAYLIST_CANONICAL_WRITER_RECEIPTS_PATH": "writer.jsonl",
        "APPLAYLIST_CANONICAL_COMPARISON_ENABLED": "1",
    }
    writer = resolve_canonical_writer_runtime_profile(env)
    comparison = resolve_canonical_legacy_comparison_profile(writer, env)
    assert comparison.enabled is False
    assert comparison.reason == "comparison_receipts_path_required"


def test_comparison_enables_only_inside_bounded_writer_profile() -> None:
    env = {
        "APP_ENV": "staging",
        "APPLAYLIST_CANONICAL_WRITER_ENABLED": "1",
        "APPLAYLIST_CANONICAL_WRITER_RECEIPTS_PATH": "writer.jsonl",
        "APPLAYLIST_CANONICAL_COMPARISON_ENABLED": "1",
        "APPLAYLIST_CANONICAL_COMPARISON_RECEIPTS_PATH": (
            "comparison.jsonl"
        ),
    }
    writer = resolve_canonical_writer_runtime_profile(env)
    comparison = resolve_canonical_legacy_comparison_profile(writer, env)
    assert comparison.enabled is True
    assert comparison.reason == "bounded_nonlive_comparison_enabled"
