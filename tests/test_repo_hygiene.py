from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.repo_hygiene_core import (
    HygieneError,
    audit_repository,
    ensure_within_root,
    quarantine_report,
    restore_manifest,
    write_report,
)
from tools.repo_hygiene_verify import run_verification


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Test User")
    _git(root, "config", "user.email", "test@example.com")
    (root / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "add", "module.py")
    _git(root, "commit", "-qm", "initial")
    return root


def _candidate(report, path: str):
    return next(candidate for candidate in report.candidates if candidate.path == path)


def test_audit_marks_untracked_cache_for_quarantine(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    cache = root / "__pycache__"
    cache.mkdir()
    (cache / "module.pyc").write_bytes(b"bytecode")

    report = audit_repository(root)

    candidate = _candidate(report, "__pycache__")
    assert candidate.category == "cache"
    assert candidate.proposed_action == "quarantine"
    assert candidate.tracked is False
    assert candidate.size_bytes == len(b"bytecode")


def test_tracked_or_modified_content_is_report_only(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    cache = root / "__pycache__"
    cache.mkdir()
    tracked = cache / "keep.py"
    tracked.write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "add", "__pycache__/keep.py")
    _git(root, "commit", "-qm", "track cache fixture")
    tracked.write_text("VALUE = 2\n", encoding="utf-8")

    report = audit_repository(root)

    candidate = _candidate(report, "__pycache__")
    assert candidate.tracked is True
    assert candidate.modified is True
    assert candidate.proposed_action == "report_only"


def test_audio_database_and_environment_files_are_never_candidates(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "music.wav").write_bytes(b"audio")
    (root / "library.sqlite").write_bytes(b"database")
    (root / ".env").write_text("SECRET=value\n", encoding="utf-8")

    report = audit_repository(root)
    paths = {candidate.path for candidate in report.candidates}

    assert "music.wav" not in paths
    assert "library.sqlite" not in paths
    assert ".env" not in paths


def test_runtime_and_heavy_directories_require_explicit_opt_in(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "artifacts").mkdir()
    (root / "artifacts" / "result.json").write_text("{}", encoding="utf-8")
    (root / ".venv").mkdir()
    (root / ".venv" / "state").write_text("generated", encoding="utf-8")

    default_report = audit_repository(root)
    generated_report = audit_repository(root, include_generated=True)
    full_report = audit_repository(root, include_generated=True, include_heavy=True)

    assert _candidate(default_report, "artifacts").proposed_action == "report_only"
    assert _candidate(default_report, ".venv").proposed_action == "report_only"
    assert _candidate(generated_report, "artifacts").proposed_action == "quarantine"
    assert _candidate(generated_report, ".venv").proposed_action == "report_only"
    assert _candidate(full_report, ".venv").proposed_action == "quarantine"


def test_untracked_identical_duplicate_is_quarantine_eligible(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    duplicate = root / "module 2.py"
    duplicate.write_text("VALUE = 1\n", encoding="utf-8")

    report = audit_repository(root)
    candidate = _candidate(report, "module 2.py")

    assert candidate.category == "suspicious_duplicate_name"
    assert candidate.canonical_path == "module.py"
    assert candidate.proposed_action == "quarantine"


def test_different_or_tracked_duplicate_is_report_only(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    duplicate = root / "module 2.py"
    duplicate.write_text("VALUE = 2\n", encoding="utf-8")

    different = _candidate(audit_repository(root), "module 2.py")
    assert different.proposed_action == "report_only"

    _git(root, "add", "module 2.py")
    _git(root, "commit", "-qm", "track historical duplicate")
    tracked = _candidate(audit_repository(root), "module 2.py")
    assert tracked.tracked is True
    assert tracked.proposed_action == "report_only"


def test_symlink_outside_root_is_not_followed_or_moved(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    protected = outside / "protected.pyc"
    protected.write_bytes(b"outside")
    link = root / "external-cache"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")

    report = audit_repository(root)

    assert protected.exists()
    assert not any(candidate.path.startswith("external-cache/") for candidate in report.candidates)
    _, count = quarantine_report(root, report, apply=True)
    assert count == 0
    assert link.is_symlink()
    assert protected.exists()


def test_quarantine_dry_run_apply_and_restore(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    cache = root / ".pytest_cache"
    cache.mkdir()
    payload = cache / "state"
    payload.write_text("cache", encoding="utf-8")
    report = audit_repository(root)

    manifest, count = quarantine_report(root, report, apply=False)
    assert manifest is None
    assert count == 1
    assert payload.exists()

    manifest, count = quarantine_report(root, report, apply=True)
    assert manifest is not None
    assert count == 1
    assert not cache.exists()
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_data["entries"][0]["original_path"] == ".pytest_cache"

    assert restore_manifest(root, manifest, apply=False) == 1
    assert not cache.exists()
    assert restore_manifest(root, manifest, apply=True) == 1
    assert payload.read_text(encoding="utf-8") == "cache"


def test_reports_are_written_only_under_ignored_state_directory(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    report = audit_repository(root)

    json_path, markdown_path = write_report(root, report)

    assert json_path.parent == root / ".repo-hygiene" / "reports"
    assert markdown_path.parent == json_path.parent
    assert json.loads(json_path.read_text(encoding="utf-8"))["repo_root"] == str(root)
    assert markdown_path.read_text(encoding="utf-8").startswith(
        "# APPLAYLIST Repository Hygiene Report"
    )


def test_verification_does_not_write_source_tree_bytecode(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    package = root / "core"
    package.mkdir()
    (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    for name in ("data", "services", "tools"):
        target = root / name
        target.mkdir()
        (target / "__init__.py").write_text("\n", encoding="utf-8")
    _git(root, "add", "core", "data", "services", "tools")
    _git(root, "commit", "-qm", "add packages")

    result = run_verification(root, python_executable=sys.executable)

    assert result["success"] is True
    assert not list(root.rglob("__pycache__"))
    assert not list(root.rglob("*.pyc"))


def test_path_containment_rejects_escape(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")

    with pytest.raises(HygieneError, match="escapes repository root"):
        ensure_within_root(root, outside)
