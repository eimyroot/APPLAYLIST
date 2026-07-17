from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


DEFAULT_AUDIO_EXTENSIONS = (
    ".aac",
    ".aif",
    ".aiff",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
)


def _text_sort_key(value: str) -> tuple[str, str]:
    return value.casefold(), value


class SymlinkPolicy(str, Enum):
    SKIP = "skip"
    ALLOW_WITHIN_ROOT = "allow_within_root"


@dataclass(frozen=True, slots=True)
class LibraryScanPolicy:
    allowed_extensions: tuple[str, ...] = DEFAULT_AUDIO_EXTENSIONS
    recursive: bool = True
    include_hidden: bool = False
    symlink_policy: SymlinkPolicy = SymlinkPolicy.SKIP
    max_entries: int = 100_000
    max_files: int = 10_000

    def __post_init__(self) -> None:
        normalized_extensions: set[str] = set()
        for extension in self.allowed_extensions:
            if not isinstance(extension, str) or not extension.strip():
                raise ValueError("allowed extensions must be non-empty strings")
            normalized = extension.strip().lower()
            if not normalized.startswith("."):
                normalized = f".{normalized}"
            normalized_extensions.add(normalized)

        if not normalized_extensions:
            raise ValueError("at least one allowed extension is required")
        if not isinstance(self.recursive, bool):
            raise TypeError("recursive must be boolean")
        if not isinstance(self.include_hidden, bool):
            raise TypeError("include_hidden must be boolean")
        if not isinstance(self.max_entries, int) or isinstance(self.max_entries, bool):
            raise TypeError("max_entries must be an integer")
        if self.max_entries <= 0:
            raise ValueError("max_entries must be positive")
        if not isinstance(self.max_files, int) or isinstance(self.max_files, bool):
            raise TypeError("max_files must be an integer")
        if self.max_files <= 0:
            raise ValueError("max_files must be positive")

        policy = self.symlink_policy
        if not isinstance(policy, SymlinkPolicy):
            try:
                policy = SymlinkPolicy(policy)
            except (TypeError, ValueError) as exc:
                raise ValueError("unsupported symlink policy") from exc

        object.__setattr__(
            self,
            "allowed_extensions",
            tuple(sorted(normalized_extensions)),
        )
        object.__setattr__(self, "symlink_policy", policy)


@dataclass(frozen=True, slots=True)
class LibraryScanIssue:
    path: str
    code: str
    detail: str

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("scan issue path is required")
        if not self.code:
            raise ValueError("scan issue code is required")
        if not self.detail:
            raise ValueError("scan issue detail is required")


@dataclass(frozen=True, slots=True)
class LibraryScanResult:
    root: str
    accepted_paths: tuple[str, ...]
    skipped: tuple[LibraryScanIssue, ...]
    errors: tuple[LibraryScanIssue, ...]
    discovered_entries: int
    cancelled: bool = False
    entry_limit_reached: bool = False
    file_limit_reached: bool = False

    def __post_init__(self) -> None:
        root = Path(self.root)
        if not root.is_absolute():
            raise ValueError("scan result root must be absolute")
        if not isinstance(self.discovered_entries, int) or isinstance(
            self.discovered_entries,
            bool,
        ):
            raise TypeError("discovered_entries must be an integer")
        if self.discovered_entries < 0:
            raise ValueError("discovered_entries must be non-negative")
        if any(not Path(path).is_absolute() for path in self.accepted_paths):
            raise ValueError("accepted paths must be absolute")
        if len(set(self.accepted_paths)) != len(self.accepted_paths):
            raise ValueError("accepted paths must be unique")
        if tuple(sorted(self.accepted_paths, key=_text_sort_key)) != self.accepted_paths:
            raise ValueError("accepted paths must be deterministically sorted")
        for value, name in (
            (self.cancelled, "cancelled"),
            (self.entry_limit_reached, "entry_limit_reached"),
            (self.file_limit_reached, "file_limit_reached"),
        ):
            if not isinstance(value, bool):
                raise TypeError(f"{name} must be boolean")

    @property
    def accepted_count(self) -> int:
        return len(self.accepted_paths)

    @property
    def complete(self) -> bool:
        return not (
            self.cancelled
            or self.entry_limit_reached
            or self.file_limit_reached
            or self.errors
        )
