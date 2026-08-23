from __future__ import annotations

import pytest

from scripts import applaylist_fresh_personal_holdout as cli
from services.intelligence.fresh_personal_holdout_runner import FreshPersonalHoldoutRunnerError


def test_verify_canonical_checkout_accepts_exact_clean_checkout(monkeypatch) -> None:
    values = {
        ("rev-parse", "HEAD"): "canonical-sha",
        ("rev-parse", "--abbrev-ref", "HEAD"): "feature/bundle-0-bootstrap",
        ("status", "--porcelain"): "",
    }
    monkeypatch.setattr(cli, "_git", lambda *args: values[args])
    cli.verify_canonical_checkout(
        canonical_sha="canonical-sha",
        canonical_branch="feature/bundle-0-bootstrap",
    )


def test_verify_canonical_checkout_rejects_wrong_head(monkeypatch) -> None:
    values = {
        ("rev-parse", "HEAD"): "wrong-sha",
        ("rev-parse", "--abbrev-ref", "HEAD"): "feature/bundle-0-bootstrap",
        ("status", "--porcelain"): "",
    }
    monkeypatch.setattr(cli, "_git", lambda *args: values[args])
    with pytest.raises(FreshPersonalHoldoutRunnerError, match="does not match declared canonical SHA"):
        cli.verify_canonical_checkout(
            canonical_sha="canonical-sha",
            canonical_branch="feature/bundle-0-bootstrap",
        )


def test_verify_canonical_checkout_rejects_dirty_tree(monkeypatch) -> None:
    values = {
        ("rev-parse", "HEAD"): "canonical-sha",
        ("rev-parse", "--abbrev-ref", "HEAD"): "feature/bundle-0-bootstrap",
        ("status", "--porcelain"): " M services/example.py",
    }
    monkeypatch.setattr(cli, "_git", lambda *args: values[args])
    with pytest.raises(FreshPersonalHoldoutRunnerError, match="clean working tree"):
        cli.verify_canonical_checkout(
            canonical_sha="canonical-sha",
            canonical_branch="feature/bundle-0-bootstrap",
        )
