from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.library.track_metadata import MetadataOrigin, TrackImportBatchResult


def _sort_key(value: str) -> tuple[str, str]:
    return value.casefold(), value


@dataclass(frozen=True, slots=True)
class PersistedTrack:
    track_id: str
    current_path: str
    metadata_provider: str
    metadata_provider_version: str
    metadata_origin: MetadataOrigin
    relinked: bool

    def __post_init__(self) -> None:
        if not self.track_id:
            raise ValueError("persisted track id is required")
        if not Path(self.current_path).is_absolute():
            raise ValueError("persisted track path must be absolute")
        if not isinstance(self.metadata_provider, str) or not self.metadata_provider.strip():
            raise ValueError("persisted metadata provider is required")
        if (
            not isinstance(self.metadata_provider_version, str)
            or not self.metadata_provider_version.strip()
        ):
            raise ValueError("persisted metadata provider version is required")
        if not isinstance(self.metadata_origin, MetadataOrigin):
            try:
                origin = MetadataOrigin(self.metadata_origin)
            except (TypeError, ValueError) as exc:
                raise ValueError("unsupported persisted metadata origin") from exc
            object.__setattr__(self, "metadata_origin", origin)
        if not isinstance(self.relinked, bool):
            raise TypeError("persisted relinked flag must be boolean")

        object.__setattr__(self, "metadata_provider", self.metadata_provider.strip())
        object.__setattr__(
            self,
            "metadata_provider_version",
            self.metadata_provider_version.strip(),
        )


@dataclass(frozen=True, slots=True)
class TrackPersistenceIssue:
    path: str
    code: str
    detail: str
    track_id: str | None = None

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("persistence issue path is required")
        if not self.code:
            raise ValueError("persistence issue code is required")
        if not self.detail:
            raise ValueError("persistence issue detail is required")
        if self.track_id is not None and not self.track_id:
            raise ValueError("persistence issue track id cannot be empty")


@dataclass(frozen=True, slots=True)
class TrackPersistenceBatchResult:
    persisted: tuple[PersistedTrack, ...]
    issues: tuple[TrackPersistenceIssue, ...]
    requested_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.requested_count, int) or isinstance(
            self.requested_count,
            bool,
        ):
            raise TypeError("requested_count must be an integer")
        if self.requested_count < 0:
            raise ValueError("requested_count must be non-negative")
        if len(self.persisted) + len(self.issues) != self.requested_count:
            raise ValueError("persistence result must account for every requested candidate")

        track_ids = tuple(item.track_id for item in self.persisted)
        if len(set(track_ids)) != len(track_ids):
            raise ValueError("persisted track ids must be unique")

        expected_persisted = tuple(
            sorted(
                self.persisted,
                key=lambda item: (_sort_key(item.current_path), item.track_id),
            )
        )
        if self.persisted != expected_persisted:
            raise ValueError("persisted tracks must be deterministically sorted")

        expected_issues = tuple(
            sorted(
                self.issues,
                key=lambda item: (
                    _sort_key(item.path),
                    _sort_key(item.code),
                    item.track_id or "",
                ),
            )
        )
        if self.issues != expected_issues:
            raise ValueError("persistence issues must be deterministically sorted")

    @property
    def complete(self) -> bool:
        return not self.issues


@dataclass(frozen=True, slots=True)
class LibraryTrackIngestionResult:
    import_result: TrackImportBatchResult
    persistence_result: TrackPersistenceBatchResult

    def __post_init__(self) -> None:
        if self.persistence_result.requested_count != len(self.import_result.candidates):
            raise ValueError("persistence result must account for all import candidates")

    @property
    def complete(self) -> bool:
        return (
            self.import_result.source_scan_complete
            and not self.import_result.issues
            and self.persistence_result.complete
        )
