from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Protocol

from core.library.persistence import (
    PersistedTrack,
    TrackPersistenceBatchResult,
    TrackPersistenceIssue,
)
from core.library.track_metadata import TrackImportBatchResult, TrackImportCandidate
from data.repositories.library_track_repository import LibraryTrackRepository


CancelRequested = Callable[[], bool]
PersistenceProgressUpdated = Callable[[int], None]


class TrackCandidateRepository(Protocol):
    def persist_candidate(self, candidate: TrackImportCandidate) -> PersistedTrack: ...


def _text_sort_key(value: str) -> tuple[str, str]:
    return value.casefold(), value


class TrackImportPersistenceService:
    def __init__(
        self,
        *,
        repository: TrackCandidateRepository | None = None,
        cancel_requested: CancelRequested | None = None,
        progress_updated: PersistenceProgressUpdated | None = None,
    ) -> None:
        self._repository = repository or LibraryTrackRepository()
        self._cancel_requested = cancel_requested or (lambda: False)
        self._progress_updated = progress_updated or (lambda _persisted: None)

    def persist(self, batch: TrackImportBatchResult) -> TrackPersistenceBatchResult:
        persisted: list[PersistedTrack] = []
        issues: list[TrackPersistenceIssue] = []
        cancelled_count = 0

        for index, candidate in enumerate(batch.candidates):
            if self._cancel_requested():
                cancelled_count = len(batch.candidates) - index
                break
            try:
                persisted.append(self._repository.persist_candidate(candidate))
                self._progress_updated(len(persisted))
            except sqlite3.DatabaseError as exc:
                issues.append(
                    TrackPersistenceIssue(
                        path=candidate.identity.source_path,
                        track_id=candidate.identity.track_id,
                        code="track_persistence_failed",
                        detail=str(exc) or "track persistence transaction failed",
                    )
                )

        self._progress_updated(len(persisted))
        ordered_persisted = tuple(
            sorted(
                persisted,
                key=lambda item: (_text_sort_key(item.current_path), item.track_id),
            )
        )
        ordered_issues = tuple(
            sorted(
                issues,
                key=lambda item: (
                    _text_sort_key(item.path),
                    _text_sort_key(item.code),
                    item.track_id or "",
                ),
            )
        )
        return TrackPersistenceBatchResult(
            persisted=ordered_persisted,
            issues=ordered_issues,
            requested_count=len(batch.candidates),
            cancelled_count=cancelled_count,
        )