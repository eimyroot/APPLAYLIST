from __future__ import annotations

from core.analysis.canonical_writer_feature_flags import (
    canonical_writer_enabled,
)


def test_canonical_writer_defaults_disabled() -> None:
    assert canonical_writer_enabled({}) is False


def test_canonical_writer_enables_only_explicit_true_value() -> None:
    assert canonical_writer_enabled(
        {"APPLAYLIST_CANONICAL_WRITER_ENABLED": "1"}
    ) is True


def test_canonical_writer_invalid_value_fails_closed() -> None:
    assert canonical_writer_enabled(
        {"APPLAYLIST_CANONICAL_WRITER_ENABLED": "maybe"}
    ) is False
