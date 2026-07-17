from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Iterable


SCHEMA_VERSION = "1"
STATE_DIR = ".repo-hygiene"

_CACHE_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tox",
    ".nox",
    "htmlcov",
}
_BUILD_DIRS = {"build", "dist"}
_GENERATED_ROOTS = {
    "artifacts",
    "exports",
    "logs",
    "tmp",
    "data/cache",
    "data/tmp",
}
_HEAVY_NAMES = {".venv", "venv", "node_modules"}
_HEAVY_PATHS = {"frontend/dist", "frontend/node_modules"}
_PROTECTED_NAMES = {".git", STATE_DIR}
_AUDIO_SUFFIXES = {
    ".aac",
    ".aif",
    ".aiff",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
}
_DATABASE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
_DUPLICATE_RE = re.compile(r"^(?P<stem>.+) (?P<copy>[2-9])(?P<suffix>\.[^/]+)?$")


class HygieneError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HygieneCandidate:
    path: str
    kind: str
    category: str
    reason: str
    size_bytes: int
    size_truncated: bool
    tracked: bool
    modified: bool
    symlink: bool
    proposed_action: str
    canonical_path: str | None = None


@dataclass(frozen=True, slots=True)
class HygieneIssue:
    path: str
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class HygieneReport:
    schema_version: str
    repo_root: str
    created_at: str
    include_generated: bool
    include_heavy: bool
    candidates: tuple[HygieneCandidate, ...]
    issues: tuple[HygieneIssue, ...]

    def summary(self) -> dict[str, int]:
        summary = {
            "candidate_count": len(self.candidates),
            "issue_count": len(self.issues),
            "quarantine_count": 0,
            "report_only_count": 0,
            "total_candidate_bytes": 0,
        }
        for candidate in self.candidates:
            summary["total_candidate_bytes"] += candidate.size_bytes
            if candidate.proposed_action == "quarantine":
                summary["quarantine_count"] += 1
            else:
                summary["report_only_count"] += 1
        return summary

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "repo_root": self.repo_root,
            "created_at": self.created_at,
            "include_generated": self.include_generated,
            "include_heavy": self.include_heavy,
            "summary": self.summary(),
            "candidates": [asdict(candidate) for candidate in self.candidates],
            "issues": [asdict(issue) for issue in self.issues],
        }


@dataclass(frozen=True, slots=True)
class QuarantineEntry:
    original_path: str
    quarantine_path: str
    kind: str
    size_bytes: int
    file_sha256: str | None


@dataclass(frozen=True, slots=True)
class QuarantineManifest:
    schema_version: str
    repo_root: str
    created_at: str
    entries: tuple[QuarantineEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "repo_root": self.repo_root,
            "created_at": self.created_at,
            "entries": [asdict(entry) for entry in self.entries],
        }


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _run_git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def resolve_repo_root(requested: str | Path) -> Path:
    candidate = Path(requested).expanduser().resolve(strict=True)
    result = _run_git(candidate, "rev-parse", "--show-toplevel")
    root = Path(result.stdout.strip()).resolve(strict=True)
    if not (root / ".git").exists():
        raise HygieneError("resolved repository root does not contain .git")
    return root


def ensure_within_root(root: Path, path: Path) -> Path:
    root = root.resolve(strict=True)
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise HygieneError(f"path escapes repository root: {path}") from exc
    return resolved


def _tracked_paths(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return {
        value.decode("utf-8", errors="surrogateescape")
        for value in result.stdout.split(b"\0")
        if value
    }


def _status_paths(root: Path) -> dict[str, str]:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "-z",
        ],
        check=True,
        capture_output=True,
    )
    records = result.stdout.split(b"\0")
    paths: dict[str, str] = {}
    index = 0
    while index < len(records):
        raw = records[index]
        index += 1
        if not raw:
            continue
        decoded = raw.decode("utf-8", errors="surrogateescape")
        if len(decoded) < 4:
            continue
        status = decoded[:2]
        path = decoded[3:]
        paths[path] = status
        if "R" in status or "C" in status:
            if index < len(records) and records[index]:
                old_path = records[index].decode("utf-8", errors="surrogateescape")
                paths[old_path] = status
                index += 1
    return paths


def _path_has_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}/")


def _contains_tracked(path: str, tracked: set[str]) -> bool:
    return any(_path_has_prefix(item, path) for item in tracked)


def _contains_modified(path: str, statuses: dict[str, str]) -> bool:
    return any(
        _path_has_prefix(item, path) and status != "??"
        for item, status in statuses.items()
    )


def _bounded_size(path: Path, *, max_entries: int = 100_000) -> tuple[int, bool]:
    if path.is_symlink():
        try:
            return path.lstat().st_size, False
        except OSError:
            return 0, False
    if path.is_file():
        try:
            return path.stat().st_size, False
        except OSError:
            return 0, False

    total = 0
    count = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    count += 1
                    if count > max_entries:
                        return total, True
                    try:
                        if entry.is_symlink():
                            total += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        else:
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total, False


def _sha256(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_duplicate_path(relative: Path) -> Path | None:
    match = _DUPLICATE_RE.fullmatch(relative.name)
    if match is None:
        return None
    canonical_name = f"{match.group('stem')}{match.group('suffix') or ''}"
    return relative.with_name(canonical_name)


def _duplicate_referenced(root: Path, relative: Path, tracked: set[str]) -> bool:
    needle = relative.as_posix()
    basename = relative.name
    for tracked_path in sorted(tracked):
        source = root / tracked_path
        if not source.is_file() or source.suffix.lower() not in {
            ".py",
            ".toml",
            ".yaml",
            ".yml",
            ".json",
            ".md",
            ".sh",
        }:
            continue
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if needle in text or basename in text:
            return True
    return False


def _classify(
    root: Path,
    relative: Path,
    *,
    is_dir: bool,
    is_symlink: bool,
    tracked: set[str],
    include_generated: bool,
    include_heavy: bool,
) -> tuple[str, str, bool, str | None] | None:
    name = relative.name
    relative_text = relative.as_posix()

    canonical = _canonical_duplicate_path(relative)
    if canonical is not None:
        canonical_absolute = root / canonical
        safe_duplicate = False
        reason = "name resembles a cloud-sync or Finder duplicate"
        if (
            not is_dir
            and not is_symlink
            and canonical_absolute.is_file()
            and relative_text not in tracked
            and canonical.as_posix() in tracked
        ):
            try:
                identical = _sha256(root / relative) == _sha256(canonical_absolute)
            except OSError:
                identical = False
            referenced = _duplicate_referenced(root, relative, tracked)
            safe_duplicate = identical and not referenced
            if safe_duplicate:
                reason = "untracked byte-identical duplicate of tracked canonical file"
            elif not identical:
                reason = "duplicate-style name differs from canonical content"
            elif referenced:
                reason = "duplicate-style name is referenced by tracked text"
        return (
            "suspicious_duplicate_name",
            reason,
            safe_duplicate,
            canonical.as_posix(),
        )

    if is_dir and (name in _CACHE_DIRS or name.endswith(".egg-info")):
        return "cache", "generated cache directory", True, None
    if is_dir and name in _BUILD_DIRS:
        return "build_output", "generated build directory", True, None
    if is_dir and (name in _HEAVY_NAMES or relative_text in _HEAVY_PATHS):
        return (
            "heavy_generated",
            "large generated dependency or environment directory",
            include_heavy,
            None,
        )
    if is_dir and relative_text in _GENERATED_ROOTS:
        return (
            "runtime_generated",
            "runtime-generated artifact, export, log or temporary directory",
            include_generated,
            None,
        )

    if not is_dir:
        suffix = relative.suffix.lower()
        if name == ".DS_Store":
            return "os_metadata", "macOS Finder metadata", True, None
        if suffix in {".pyc", ".pyo", ".swp", ".swo", ".tmp"} or name.endswith("~"):
            return "temporary_file", "generated bytecode or editor temporary file", True, None
        if name == ".coverage":
            return "test_output", "generated coverage data", True, None
        if suffix in _DATABASE_SUFFIXES or suffix in _AUDIO_SUFFIXES:
            return None
        if name == ".env" or name.startswith(".env."):
            return None

    return None


def _iter_entries(root: Path) -> Iterable[tuple[Path, bool, bool]]:
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(
                os.scandir(current),
                key=lambda entry: (entry.name.casefold(), entry.name),
            )
        except OSError:
            continue
        for entry in entries:
            if current == root and entry.name in _PROTECTED_NAMES:
                continue
            path = Path(entry.path)
            relative = path.relative_to(root)
            is_symlink = entry.is_symlink()
            is_dir = entry.is_dir(follow_symlinks=False)
            yield relative, is_dir, is_symlink
            if is_dir and not is_symlink:
                stack.append(path)


def audit_repository(
    root: Path,
    *,
    include_generated: bool = False,
    include_heavy: bool = False,
) -> HygieneReport:
    root = root.resolve(strict=True)
    tracked = _tracked_paths(root)
    statuses = _status_paths(root)
    candidates: list[HygieneCandidate] = []
    issues: list[HygieneIssue] = []
    selected_prefixes: set[str] = set()

    for relative, is_dir, is_symlink in _iter_entries(root):
        relative_text = relative.as_posix()
        if any(_path_has_prefix(relative_text, prefix) for prefix in selected_prefixes):
            continue

        classification = _classify(
            root,
            relative,
            is_dir=is_dir,
            is_symlink=is_symlink,
            tracked=tracked,
            include_generated=include_generated,
            include_heavy=include_heavy,
        )
        if classification is None:
            continue

        category, reason, allowed, canonical_path = classification
        contains_tracked = _contains_tracked(relative_text, tracked)
        contains_modified = _contains_modified(relative_text, statuses)
        absolute = root / relative
        size_bytes, size_truncated = _bounded_size(absolute)

        proposed_action = "quarantine"
        if contains_tracked:
            proposed_action = "report_only"
            reason = f"{reason}; contains tracked content"
        elif contains_modified:
            proposed_action = "report_only"
            reason = f"{reason}; contains modified tracked content"
        elif is_symlink:
            proposed_action = "report_only"
            reason = f"{reason}; symlinks are never moved automatically"
        elif not allowed:
            proposed_action = "report_only"
            reason = f"{reason}; explicit opt-in required"

        candidates.append(
            HygieneCandidate(
                path=relative_text,
                kind="directory" if is_dir else "file",
                category=category,
                reason=reason,
                size_bytes=size_bytes,
                size_truncated=size_truncated,
                tracked=contains_tracked,
                modified=contains_modified,
                symlink=is_symlink,
                proposed_action=proposed_action,
                canonical_path=canonical_path,
            )
        )
        if is_dir:
            selected_prefixes.add(relative_text)

    candidates.sort(key=lambda item: (item.path.casefold(), item.path))
    issues.sort(key=lambda item: (item.path.casefold(), item.path, item.code))
    return HygieneReport(
        schema_version=SCHEMA_VERSION,
        repo_root=str(root),
        created_at=datetime.now(timezone.utc).isoformat(),
        include_generated=include_generated,
        include_heavy=include_heavy,
        candidates=tuple(candidates),
        issues=tuple(issues),
    )


def report_markdown(report: HygieneReport) -> str:
    summary = report.summary()
    lines = [
        "# APPLAYLIST Repository Hygiene Report",
        "",
        f"- Repository: `{report.repo_root}`",
        f"- Created: `{report.created_at}`",
        f"- Candidates: **{summary['candidate_count']}**",
        f"- Quarantine eligible: **{summary['quarantine_count']}**",
        f"- Report only: **{summary['report_only_count']}**",
        f"- Candidate bytes: **{summary['total_candidate_bytes']}**",
        "",
        "## Candidates",
        "",
        "| Action | Path | Category | Bytes | Tracked | Modified | Reason |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for candidate in report.candidates:
        reason = candidate.reason.replace("|", "\\|")
        path = candidate.path.replace("|", "\\|")
        lines.append(
            "| "
            f"{candidate.proposed_action} | `{path}` | {candidate.category} | "
            f"{candidate.size_bytes} | {candidate.tracked} | {candidate.modified} | "
            f"{reason} |"
        )
    if not report.candidates:
        lines.append("| — | — | — | 0 | False | False | No candidates found |")

    lines.extend(["", "## Issues", ""])
    if report.issues:
        for issue in report.issues:
            lines.append(f"- `{issue.code}` `{issue.path}` — {issue.detail}")
    else:
        lines.append("No audit issues.")
    lines.append("")
    return "\n".join(lines)


def write_report(root: Path, report: HygieneReport, *, label: str = "audit") -> tuple[Path, Path]:
    report_dir = root / STATE_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    json_path = report_dir / f"{stamp}-{label}.json"
    md_path = report_dir / f"{stamp}-{label}.md"
    json_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(report_markdown(report), encoding="utf-8")
    return json_path, md_path


def quarantine_report(root: Path, report: HygieneReport, *, apply: bool) -> tuple[Path | None, int]:
    eligible = [
        candidate
        for candidate in report.candidates
        if candidate.proposed_action == "quarantine"
    ]
    if not apply:
        return None, len(eligible)

    root = root.resolve(strict=True)
    stamp = utc_stamp()
    quarantine_root = root / STATE_DIR / "quarantine" / stamp
    payload_root = quarantine_root / "payload"
    entries: list[QuarantineEntry] = []

    for candidate in eligible:
        source = ensure_within_root(root, root / candidate.path)
        if not source.exists() and not source.is_symlink():
            continue
        destination = ensure_within_root(root, payload_root / candidate.path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() or destination.is_symlink():
            raise HygieneError(f"quarantine destination already exists: {destination}")
        file_digest = None
        if source.is_file() and not source.is_symlink():
            file_digest = _sha256(source)
        shutil.move(str(source), str(destination))
        entries.append(
            QuarantineEntry(
                original_path=candidate.path,
                quarantine_path=destination.relative_to(root).as_posix(),
                kind=candidate.kind,
                size_bytes=candidate.size_bytes,
                file_sha256=file_digest,
            )
        )

    manifest = QuarantineManifest(
        schema_version=SCHEMA_VERSION,
        repo_root=str(root),
        created_at=datetime.now(timezone.utc).isoformat(),
        entries=tuple(entries),
    )
    manifest_path = quarantine_root / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path, len(entries)


def restore_manifest(root: Path, manifest_path: Path, *, apply: bool) -> int:
    root = root.resolve(strict=True)
    manifest_path = ensure_within_root(root, manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise HygieneError("unsupported quarantine manifest schema")
    if Path(payload.get("repo_root", "")).resolve() != root:
        raise HygieneError("quarantine manifest belongs to another repository")

    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise HygieneError("invalid quarantine manifest entries")
    if not apply:
        return len(entries)

    restored = 0
    for raw in reversed(entries):
        if not isinstance(raw, dict):
            raise HygieneError("invalid quarantine manifest entry")
        original = ensure_within_root(root, root / str(raw["original_path"]))
        quarantined = ensure_within_root(root, root / str(raw["quarantine_path"]))
        if original.exists() or original.is_symlink():
            raise HygieneError(f"restore target already exists: {original}")
        if not quarantined.exists() and not quarantined.is_symlink():
            raise HygieneError(f"quarantined path missing: {quarantined}")
        expected_digest = raw.get("file_sha256")
        if expected_digest and quarantined.is_file() and _sha256(quarantined) != expected_digest:
            raise HygieneError(f"quarantined file digest changed: {quarantined}")
        original.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(quarantined), str(original))
        restored += 1
    return restored


def run_verification(root: Path, *, python_executable: str) -> dict[str, object]:
    root = root.resolve(strict=True)
    audit = audit_repository(root)
    tracked_quarantine = [
        candidate.path
        for candidate in audit.candidates
        if candidate.tracked and candidate.proposed_action == "quarantine"
    ]
    checks: list[dict[str, object]] = []

    commands = [
        ("git_diff_check", ["git", "-C", str(root), "diff", "--check"]),
        (
            "compile",
            [
                python_executable,
                "-m",
                "compileall",
                "-q",
                "api",
                "core",
                "data",
                "services",
                "workers",
                "tools",
            ],
        ),
        (
            "imports",
            [python_executable, "-c", "import core, data, services, tools"],
        ),
    ]
    for name, command in commands:
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
        )
        checks.append(
            {
                "name": name,
                "success": completed.returncode == 0,
                "returncode": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
            }
        )

    status = _run_git(root, "status", "--short", "--branch").stdout.strip()
    return {
        "repo_root": str(root),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_status": status,
        "tracked_quarantine_violation": tracked_quarantine,
        "audit_summary": audit.summary(),
        "checks": checks,
        "success": not tracked_quarantine and all(check["success"] for check in checks),
    }
