from __future__ import annotations

import sqlite3
from typing import Protocol

from core.library.persistence import (
    PersistedTrack,
    TrackPersistenceBatchResult,
    TrackPersistenceIssue,
)
from core.library.track_metadata import TrackImportBatchResult, TrackImportCandidate
from data.repositories.library_track_repository import LibraryTrackRepository


class TrackCandidateRepository(Protocol):
    def persist_candidate(self, candidate: TrackImportCandidate) -> PersistedTrack: ...


def _text_sort_key(value: str) -> tuple[str, str]:
    return value.casefold(), value


class TrackImportPersistenceService:
    def __init__(
        self,
        *,
        repository: TrackCandidateRepository | None = None,
    ) -> None:
        self._repository = repository or LibraryTrackRepository()

    def persist(self, batch: TrackImportBatchResult) -> TrackPersistenceBatchResult:
        persisted: list[PersistedTrack] = []
        issues: list[TrackPersistenceIssue] = []

        for candidate in batch.candidates:
            try:
                persisted.append(self._repository.persist_candidate(candidate))
            except sqlite3.DatabaseError as exc:
                issues.append(
                    TrackPersistenceIssue(
                        path=candidate.identity.source_path,
                        track_id=candidate.identity.track_id,
                        code="track_persistence_failed",
                        detail=str(exc) or "track persistence transaction failed",
                    )
                )

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
        )
