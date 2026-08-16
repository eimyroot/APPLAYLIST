from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from core.library.contracts import (
    LibraryScanIssue,
    LibraryScanPolicy,
    LibraryScanResult,
    SymlinkPolicy,
)


CancelRequested = Callable[[], bool]
ScanProgressUpdated = Callable[[int, int], None]
DirectoryIdentity = tuple[int, int]


class LibraryScanner:
    def __init__(
        self,
        *,
        policy: LibraryScanPolicy | None = None,
        cancel_requested: CancelRequested | None = None,
        progress_updated: ScanProgressUpdated | None = None,
    ) -> None:
        self.policy = policy or LibraryScanPolicy()
        self._cancel_requested = cancel_requested or (lambda: False)
        self._progress_updated = progress_updated or (
            lambda _discovered_entries, _accepted: None
        )

    def scan(self, root: str | Path) -> LibraryScanResult:
        requested_root = Path(root).expanduser()
        if not requested_root.is_absolute():
            raise ValueError("library root must be absolute")

        resolved_root = requested_root.resolve(strict=False)
        root_text = str(resolved_root)
        errors: list[LibraryScanIssue] = []
        skipped: list[LibraryScanIssue] = []

        try:
            root_exists = resolved_root.exists()
        except OSError:
            root_exists = False
        if not root_exists:
            errors.append(
                self._issue(
                    resolved_root,
                    "root_not_found",
                    "library root does not exist",
                )
            )
            return self._result(root_text, errors=errors)

        try:
            root_is_directory = resolved_root.is_dir()
        except OSError:
            root_is_directory = False
        if not root_is_directory:
            errors.append(
                self._issue(
                    resolved_root,
                    "root_not_directory",
                    "library root is not a directory",
                )
            )
            return self._result(root_text, errors=errors)

        accepted: set[str] = set()
        discovered_entries = 0
        cancelled = False
        entry_limit_reached = False
        file_limit_reached = False
        stop = False

        root_identity = self._directory_identity(resolved_root)
        if root_identity is None:
            errors.append(
                self._issue(
                    resolved_root,
                    "root_unreadable",
                    "library root cannot be inspected",
                )
            )
            return self._result(root_text, errors=errors)

        visited_directories: set[DirectoryIdentity] = {root_identity}
        pending_directories: list[Path] = [resolved_root]
        self._progress_updated(0, 0)

        while pending_directories and not stop:
            if self._cancel_requested():
                cancelled = True
                break

            current_directory = pending_directories.pop()
            try:
                entries = sorted(
                    os.scandir(current_directory),
                    key=lambda entry: (entry.name.casefold(), entry.name),
                )
            except OSError:
                errors.append(
                    self._issue(
                        current_directory,
                        "directory_unreadable",
                        "directory cannot be read",
                    )
                )
                continue

            child_directories: list[Path] = []
            for entry in entries:
                if self._cancel_requested():
                    cancelled = True
                    stop = True
                    break

                entry_path = Path(entry.path)
                if discovered_entries >= self.policy.max_entries:
                    entry_limit_reached = True
                    skipped.append(
                        self._issue(
                            entry_path,
                            "entry_limit_reached",
                            "maximum scanned entry count reached",
                        )
                    )
                    stop = True
                    break
                discovered_entries += 1
                self._progress_updated(discovered_entries, len(accepted))

                if not self.policy.include_hidden and entry.name.startswith("."):
                    skipped.append(
                        self._issue(
                            entry_path,
                            "hidden_entry_skipped",
                            "hidden entry excluded by scan policy",
                        )
                    )
                    continue

                try:
                    is_symlink = entry.is_symlink()
                except OSError:
                    errors.append(
                        self._issue(
                            entry_path,
                            "entry_unreadable",
                            "entry type cannot be inspected",
                        )
                    )
                    continue

                if is_symlink:
                    stop = self._handle_symlink(
                        entry_path=entry_path,
                        root=resolved_root,
                        accepted=accepted,
                        skipped=skipped,
                        errors=errors,
                        child_directories=child_directories,
                        visited_directories=visited_directories,
                    )
                    self._progress_updated(discovered_entries, len(accepted))
                    if stop:
                        file_limit_reached = True
                        break
                    continue

                try:
                    is_directory = entry.is_dir(follow_symlinks=False)
                    is_file = entry.is_file(follow_symlinks=False)
                except OSError:
                    errors.append(
                        self._issue(
                            entry_path,
                            "entry_unreadable",
                            "entry type cannot be inspected",
                        )
                    )
                    continue

                if is_directory:
                    if not self.policy.recursive:
                        skipped.append(
                            self._issue(
                                entry_path,
                                "directory_skipped_non_recursive",
                                "directory excluded by non-recursive policy",
                            )
                        )
                        continue
                    resolved_directory = self._resolve_within_root(
                        entry_path,
                        resolved_root,
                    )
                    if resolved_directory is None:
                        errors.append(
                            self._issue(
                                entry_path,
                                "directory_unreadable",
                                "directory cannot be resolved within root",
                            )
                        )
                        continue
                    self._queue_directory(
                        directory=resolved_directory,
                        source_path=entry_path,
                        child_directories=child_directories,
                        visited_directories=visited_directories,
                        skipped=skipped,
                        errors=errors,
                    )
                    continue

                if is_file:
                    resolved_file = self._resolve_within_root(entry_path, resolved_root)
                    if resolved_file is None:
                        errors.append(
                            self._issue(
                                entry_path,
                                "file_unreadable",
                                "file cannot be resolved within root",
                            )
                        )
                        continue
                    if self._accept_file(
                        resolved_file,
                        accepted=accepted,
                        skipped=skipped,
                    ):
                        file_limit_reached = True
                        stop = True
                    self._progress_updated(discovered_entries, len(accepted))
                    if stop:
                        break
                    continue

                skipped.append(
                    self._issue(
                        entry_path,
                        "unsupported_entry_type",
                        "entry is neither a regular file nor a directory",
                    )
                )

            if not stop:
                child_directories.sort(key=self._path_sort_key, reverse=True)
                pending_directories.extend(child_directories)

        self._progress_updated(discovered_entries, len(accepted))
        accepted_paths = tuple(sorted(accepted, key=self._text_sort_key))
        return LibraryScanResult(
            root=root_text,
            accepted_paths=accepted_paths,
            skipped=tuple(skipped),
            errors=tuple(errors),
            discovered_entries=discovered_entries,
            cancelled=cancelled,
            entry_limit_reached=entry_limit_reached,
            file_limit_reached=file_limit_reached,
        )

    def _handle_symlink(
        self,
        *,
        entry_path: Path,
        root: Path,
        accepted: set[str],
        skipped: list[LibraryScanIssue],
        errors: list[LibraryScanIssue],
        child_directories: list[Path],
        visited_directories: set[DirectoryIdentity],
    ) -> bool:
        if self.policy.symlink_policy == SymlinkPolicy.SKIP:
            skipped.append(
                self._issue(
                    entry_path,
                    "symlink_skipped",
                    "symlink excluded by scan policy",
                )
            )
            return False

        try:
            target = entry_path.resolve(strict=True)
        except OSError:
            errors.append(
                self._issue(
                    entry_path,
                    "symlink_unreadable",
                    "symlink target cannot be resolved",
                )
            )
            return False

        if not target.is_relative_to(root):
            skipped.append(
                self._issue(
                    entry_path,
                    "symlink_outside_root",
                    "symlink target escapes the selected root",
                )
            )
            return False

        try:
            if target.is_dir():
                if not self.policy.recursive:
                    skipped.append(
                        self._issue(
                            entry_path,
                            "directory_skipped_non_recursive",
                            "symlinked directory excluded by non-recursive policy",
                        )
                    )
                    return False
                self._queue_directory(
                    directory=target,
                    source_path=entry_path,
                    child_directories=child_directories,
                    visited_directories=visited_directories,
                    skipped=skipped,
                    errors=errors,
                )
                return False
            if target.is_file():
                return self._accept_file(
                    target,
                    accepted=accepted,
                    skipped=skipped,
                    issue_path=entry_path,
                )
        except OSError:
            errors.append(
                self._issue(
                    entry_path,
                    "symlink_unreadable",
                    "symlink target cannot be inspected",
                )
            )
            return False

        skipped.append(
            self._issue(
                entry_path,
                "unsupported_entry_type",
                "symlink target is not a regular file or directory",
            )
        )
        return False

    def _accept_file(
        self,
        file_path: Path,
        *,
        accepted: set[str],
        skipped: list[LibraryScanIssue],
        issue_path: Path | None = None,
    ) -> bool:
        evidence_path = issue_path or file_path
        if file_path.suffix.lower() not in self.policy.allowed_extensions:
            skipped.append(
                self._issue(
                    evidence_path,
                    "unsupported_extension",
                    "file extension excluded by scan policy",
                )
            )
            return False

        normalized = str(file_path)
        if normalized in accepted:
            skipped.append(
                self._issue(
                    evidence_path,
                    "duplicate_target",
                    "resolved file was already accepted",
                )
            )
            return False

        if len(accepted) >= self.policy.max_files:
            skipped.append(
                self._issue(
                    evidence_path,
                    "file_limit_reached",
                    "maximum accepted file count reached",
                )
            )
            return True

        accepted.add(normalized)
        return False

    def _queue_directory(
        self,
        *,
        directory: Path,
        source_path: Path,
        child_directories: list[Path],
        visited_directories: set[DirectoryIdentity],
        skipped: list[LibraryScanIssue],
        errors: list[LibraryScanIssue],
    ) -> None:
        identity = self._directory_identity(directory)
        if identity is None:
            errors.append(
                self._issue(
                    source_path,
                    "directory_unreadable",
                    "directory identity cannot be inspected",
                )
            )
            return
        if identity in visited_directories:
            skipped.append(
                self._issue(
                    source_path,
                    "duplicate_directory",
                    "directory target was already scheduled or scanned",
                )
            )
            return
        visited_directories.add(identity)
        child_directories.append(directory)

    @staticmethod
    def _directory_identity(path: Path) -> DirectoryIdentity | None:
        try:
            stat_result = path.stat()
        except OSError:
            return None
        return stat_result.st_dev, stat_result.st_ino

    @staticmethod
    def _resolve_within_root(path: Path, root: Path) -> Path | None:
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            return None
        if not resolved.is_relative_to(root):
            return None
        return resolved

    @staticmethod
    def _issue(path: Path, code: str, detail: str) -> LibraryScanIssue:
        return LibraryScanIssue(path=str(path.absolute()), code=code, detail=detail)

    @staticmethod
    def _text_sort_key(value: str) -> tuple[str, str]:
        return value.casefold(), value

    @classmethod
    def _path_sort_key(cls, value: Path) -> tuple[str, str]:
        return cls._text_sort_key(str(value))

    @staticmethod
    def _result(
        root: str,
        *,
        errors: list[LibraryScanIssue],
    ) -> LibraryScanResult:
        return LibraryScanResult(
            root=root,
            accepted_paths=(),
            skipped=(),
            errors=tuple(errors),
            discovered_entries=0,
        )