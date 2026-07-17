from __future__ import annotations

from core.library.contracts import LibraryScanResult
from core.library.persistence import LibraryTrackIngestionResult
from services.library.importer import LibraryCandidateImporter
from services.library.metadata import TinyTagMetadataReader
from services.library.persistence import TrackImportPersistenceService


class LibraryTrackIngestionService:
    def __init__(
        self,
        *,
        importer: LibraryCandidateImporter | None = None,
        persistence: TrackImportPersistenceService | None = None,
    ) -> None:
        self._importer = importer or LibraryCandidateImporter(
            metadata_reader=TinyTagMetadataReader()
        )
        self._persistence = persistence or TrackImportPersistenceService()

    def ingest(self, scan_result: LibraryScanResult) -> LibraryTrackIngestionResult:
        import_result = self._importer.import_scan(scan_result)
        persistence_result = self._persistence.persist(import_result)
        return LibraryTrackIngestionResult(
            import_result=import_result,
            persistence_result=persistence_result,
        )
