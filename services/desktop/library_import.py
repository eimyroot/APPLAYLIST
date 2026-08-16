from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from core.library.contracts import LibraryScanIssue, LibraryScanResult
from core.library.persistence import (
    LibraryTrackIngestionResult,
    TrackPersistenceIssue,
)
from core.library.track_metadata import TrackImportIssue
from services.library.ingestion import LibraryTrackIngestionService
from services.library.scanner import LibraryScanner


class DesktopLibraryImportError(ValueError):
    """Raised when the trusted desktop host supplies an invalid library folder."""


class DesktopLibraryIssueStage(StrEnum):
    SCAN_SKIPPED = "scan_skipped"
    SCAN_ERROR = "scan_error"
    IMPORT = "import"
    PERSISTENCE = "persistence"


class DesktopLibraryImportPhase(StrEnum):
    STARTING = "starting"
    SCANNING = "scanning"
    IMPORTING = "importing"
    PERSISTING = "persisting"
    FINALIZING = "finalizing"


@dataclass(frozen=True, slots=True)
class DesktopLibraryProgress:
    phase: DesktopLibraryImportPhase
    discovered_entries: int
    accepted_count: int
    imported_count: int
    persisted_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.phase, DesktopLibraryImportPhase):
            object.__setattr__(self, "phase", DesktopLibraryImportPhase(self.phase))
        for value, name in (
            (self.discovered_entries, "discovered_entries"),
            (self.accepted_count, "accepted_count"),
            (self.imported_count, "imported_count"),
            (self.persisted_count, "persisted_count"),
        ):
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{name} must be an integer")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")

    def to_payload(self) -> dict[str, object]:
        return {
            "phase": self.phase.value,
            "counts": {
                "discovered_entries": self.discovered_entries,
                "accepted": self.accepted_count,
                "imported": self.imported_count,
                "persisted": self.persisted_count,
            },
        }


@dataclass(frozen=True, slots=True)
class DesktopLibraryIssue:
    stage: DesktopLibraryIssueStage
    code: str
    file_name: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.stage, DesktopLibraryIssueStage):
            object.__setattr__(self, "stage", DesktopLibraryIssueStage(self.stage))
        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError("desktop library issue code is required")
        object.__setattr__(self, "code", self.code.strip())
        if self.file_name is not None:
            if not isinstance(self.file_name, str):
                raise TypeError("desktop library issue file name must be text")
            normalized = self.file_name.strip()
            object.__setattr__(self, "file_name", normalized or None)

    def to_payload(self) -> dict[str, object]:
        return {
            "stage": self.stage.value,
            "code": self.code,
            "file_name": self.file_name,
        }


@dataclass(frozen=True, slots=True)
class DesktopLibraryTrack:
    track_id: str
    file_name: str
    title: str | None
    artist: str | None
    album: str | None
    genre: str | None
    duration_seconds: float | None
    metadata_origin: str
    relinked: bool

    def __post_init__(self) -> None:
        if not self.track_id:
            raise ValueError("desktop library track id is required")
        if not self.file_name:
            raise ValueError("desktop library track file name is required")
        if not self.metadata_origin:
            raise ValueError("desktop library metadata origin is required")
        if not isinstance(self.relinked, bool):
            raise TypeError("desktop library relinked flag must be boolean")

    def to_payload(self) -> dict[str, object]:
        return {
            "track_id": self.track_id,
            "file_name": self.file_name,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "genre": self.genre,
            "duration_seconds": self.duration_seconds,
            "metadata_origin": self.metadata_origin,
            "relinked": self.relinked,
        }


@dataclass(frozen=True, slots=True)
class DesktopLibraryImportResult:
    folder_name: str
    tracks: tuple[DesktopLibraryTrack, ...]
    issues: tuple[DesktopLibraryIssue, ...]
    discovered_entries: int
    accepted_count: int
    imported_count: int
    persisted_count: int
    cancelled: bool
    entry_limit_reached: bool
    file_limit_reached: bool
    complete: bool

    def to_payload(self) -> dict[str, object]:
        return {
            "folder_name": self.folder_name,
            "tracks": [track.to_payload() for track in self.tracks],
            "issues": [issue.to_payload() for issue in self.issues],
            "counts": {
                "discovered_entries": self.discovered_entries,
                "accepted": self.accepted_count,
                "imported": self.imported_count,
                "persisted": self.persisted_count,
            },
            "cancelled": self.cancelled,
            "entry_limit_reached": self.entry_limit_reached,
            "file_limit_reached": self.file_limit_reached,
            "complete": self.complete,
        }


class LibraryScanPort(Protocol):
    def scan(self, root: str | Path) -> LibraryScanResult: ...


class LibraryIngestionPort(Protocol):
    def ingest(self, scan_result: LibraryScanResult) -> LibraryTrackIngestionResult: ...


CancelRequested = Callable[[], bool]
ProgressUpdated = Callable[[DesktopLibraryProgress], None]


def _file_name(path: str) -> str | None:
    name = Path(path).name.strip()
    return name or None


def _issue_sort_key(issue: DesktopLibraryIssue) -> tuple[str, str, str]:
    return (
        issue.stage.value,
        issue.code.casefold(),
        (issue.file_name or "").casefold(),
    )


class DesktopLibraryImportService:
    """Trusted desktop-core application service for one bounded library import.

    This service is not a renderer authorization boundary. The caller must be the
    trusted desktop core and must pass only a folder selected through the native
    host dialog/capability flow. Returned DTOs deliberately omit absolute paths.
    """

    def __init__(
        self,
        *,
        scanner: LibraryScanPort | None = None,
        ingestion: LibraryIngestionPort | None = None,
        cancel_requested: CancelRequested | None = None,
        progress_updated: ProgressUpdated | None = None,
    ) -> None:
        self._scanner = scanner
        self._ingestion = ingestion
        self._cancel_requested = cancel_requested or (lambda: False)
        self._progress_updated = progress_updated or (lambda _progress: None)

    def import_folder(self, folder: str | Path) -> DesktopLibraryImportResult:
        requested = Path(folder).expanduser()
        if not requested.is_absolute():
            raise DesktopLibraryImportError(
                "desktop library folder must be an absolute host-selected path"
            )

        counts = {
            "discovered_entries": 0,
            "accepted": 0,
            "imported": 0,
            "persisted": 0,
        }
        self._emit_progress(DesktopLibraryImportPhase.STARTING, counts)

        scanner = self._scanner or LibraryScanner(cancel_requested=self._cancel_requested)
        self._emit_progress(DesktopLibraryImportPhase.SCANNING, counts)
        scan = scanner.scan(requested)
        counts["discovered_entries"] = scan.discovered_entries
        counts["accepted"] = scan.accepted_count
        self._emit_progress(DesktopLibraryImportPhase.IMPORTING, counts)

        def import_progress(imported: int) -> None:
            counts["imported"] = max(counts["imported"], imported)
            self._emit_progress(DesktopLibraryImportPhase.IMPORTING, counts)

        def persistence_progress(persisted: int) -> None:
            counts["persisted"] = max(counts["persisted"], persisted)
            self._emit_progress(DesktopLibraryImportPhase.PERSISTING, counts)

        ingestion_service = self._ingestion or LibraryTrackIngestionService(
            cancel_requested=self._cancel_requested,
            import_progress_updated=import_progress,
            persistence_progress_updated=persistence_progress,
        )
        ingestion = ingestion_service.ingest(scan)

        if ingestion.import_result.source_scan_complete != scan.complete:
            raise RuntimeError("library ingestion scan-complete state drifted")

        counts["imported"] = len(ingestion.import_result.candidates)
        counts["persisted"] = len(ingestion.persistence_result.persisted)
        self._emit_progress(DesktopLibraryImportPhase.FINALIZING, counts)

        candidates_by_id = {
            candidate.identity.track_id: candidate
            for candidate in ingestion.import_result.candidates
        }

        tracks: list[DesktopLibraryTrack] = []
        for persisted in ingestion.persistence_result.persisted:
            candidate = candidates_by_id.get(persisted.track_id)
            if candidate is None:
                raise RuntimeError("persisted track is missing its import candidate")
            metadata = candidate.metadata
            tracks.append(
                DesktopLibraryTrack(
                    track_id=persisted.track_id,
                    file_name=_file_name(persisted.current_path) or "track",
                    title=metadata.title,
                    artist=metadata.artist,
                    album=metadata.album,
                    genre=metadata.genre,
                    duration_seconds=metadata.duration_seconds,
                    metadata_origin=persisted.metadata_origin.value,
                    relinked=persisted.relinked,
                )
            )

        issues = [
            *(
                self._scan_issue(issue, DesktopLibraryIssueStage.SCAN_SKIPPED)
                for issue in scan.skipped
            ),
            *(
                self._scan_issue(issue, DesktopLibraryIssueStage.SCAN_ERROR)
                for issue in scan.errors
            ),
            *(self._import_issue(issue) for issue in ingestion.import_result.issues),
            *(
                self._persistence_issue(issue)
                for issue in ingestion.persistence_result.issues
            ),
        ]

        ordered_tracks = tuple(
            sorted(
                tracks,
                key=lambda track: (
                    track.file_name.casefold(),
                    track.file_name,
                    track.track_id,
                ),
            )
        )
        ordered_issues = tuple(sorted(issues, key=_issue_sort_key))

        resolved_root = Path(scan.root)
        folder_name = resolved_root.name or resolved_root.anchor or "Library"
        cancelled = (
            scan.cancelled
            or ingestion.import_result.cancelled
            or ingestion.persistence_result.cancelled_count > 0
        )

        return DesktopLibraryImportResult(
            folder_name=folder_name,
            tracks=ordered_tracks,
            issues=ordered_issues,
            discovered_entries=scan.discovered_entries,
            accepted_count=scan.accepted_count,
            imported_count=len(ingestion.import_result.candidates),
            persisted_count=len(ingestion.persistence_result.persisted),
            cancelled=cancelled,
            entry_limit_reached=scan.entry_limit_reached,
            file_limit_reached=scan.file_limit_reached,
            complete=scan.complete and ingestion.complete and not cancelled,
        )

    def _emit_progress(
        self,
        phase: DesktopLibraryImportPhase,
        counts: dict[str, int],
    ) -> None:
        self._progress_updated(
            DesktopLibraryProgress(
                phase=phase,
                discovered_entries=counts["discovered_entries"],
                accepted_count=counts["accepted"],
                imported_count=counts["imported"],
                persisted_count=counts["persisted"],
            )
        )

    @staticmethod
    def _scan_issue(
        issue: LibraryScanIssue,
        stage: DesktopLibraryIssueStage,
    ) -> DesktopLibraryIssue:
        return DesktopLibraryIssue(
            stage=stage,
            code=issue.code,
            file_name=_file_name(issue.path),
        )

    @staticmethod
    def _import_issue(issue: TrackImportIssue) -> DesktopLibraryIssue:
        return DesktopLibraryIssue(
            stage=DesktopLibraryIssueStage.IMPORT,
            code=issue.code,
            file_name=_file_name(issue.path),
        )

    @staticmethod
    def _persistence_issue(issue: TrackPersistenceIssue) -> DesktopLibraryIssue:
        return DesktopLibraryIssue(
            stage=DesktopLibraryIssueStage.PERSISTENCE,
            code=issue.code,
            file_name=_file_name(issue.path),
        )