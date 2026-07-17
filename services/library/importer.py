from __future__ import annotations

from collections.abc import Iterable

from core.library.contracts import LibraryScanResult
from core.library.track_metadata import (
    TrackImportBatchResult,
    TrackImportCandidate,
    TrackImportIssue,
)
from services.library.identity import ContentTrackIdentityService, TrackIdentityError
from services.library.metadata import (
    FilenameFallbackMetadataReader,
    MetadataReadError,
    TrackMetadataReader,
)


def _text_sort_key(value: str) -> tuple[str, str]:
    return value.casefold(), value


class LibraryCandidateImporter:
    def __init__(
        self,
        *,
        identity_service: ContentTrackIdentityService | None = None,
        metadata_reader: TrackMetadataReader | None = None,
    ) -> None:
        self._identity_service = identity_service or ContentTrackIdentityService()
        self._metadata_reader = metadata_reader or FilenameFallbackMetadataReader()

    def import_scan(self, scan_result: LibraryScanResult) -> TrackImportBatchResult:
        candidates: list[TrackImportCandidate] = []
        issues: list[TrackImportIssue] = []
        seen_track_ids: dict[str, str] = {}

        for path in sorted(scan_result.accepted_paths, key=_text_sort_key):
            try:
                identity = self._identity_service.identify(path)
                metadata = self._metadata_reader.read(identity.source_path)
            except TrackIdentityError as exc:
                issues.append(
                    TrackImportIssue(
                        path=exc.path,
                        code=exc.code,
                        detail=exc.detail,
                    )
                )
                continue
            except MetadataReadError as exc:
                issues.append(
                    TrackImportIssue(
                        path=exc.path,
                        code=exc.code,
                        detail=exc.detail,
                    )
                )
                continue
            except (TypeError, ValueError) as exc:
                issues.append(
                    TrackImportIssue(
                        path=path,
                        code="metadata_output_invalid",
                        detail=str(exc) or "metadata reader returned invalid output",
                    )
                )
                continue

            first_path = seen_track_ids.get(identity.track_id)
            if first_path is not None:
                issues.append(
                    TrackImportIssue(
                        path=identity.source_path,
                        code="duplicate_content",
                        detail=f"same content already accepted from {first_path}",
                    )
                )
                continue

            candidate = TrackImportCandidate(identity=identity, metadata=metadata)
            candidates.append(candidate)
            seen_track_ids[identity.track_id] = identity.source_path

        ordered_candidates = tuple(
            sorted(
                candidates,
                key=lambda candidate: _text_sort_key(candidate.identity.source_path),
            )
        )
        ordered_issues = tuple(
            sorted(
                issues,
                key=lambda issue: (
                    issue.path.casefold(),
                    issue.path,
                    issue.code.casefold(),
                    issue.code,
                ),
            )
        )
        return TrackImportBatchResult(
            candidates=ordered_candidates,
            issues=ordered_issues,
            source_scan_complete=scan_result.complete,
        )

    def import_paths(
        self,
        paths: Iterable[str],
        *,
        source_scan_complete: bool = True,
    ) -> TrackImportBatchResult:
        ordered_paths = tuple(sorted(set(paths), key=_text_sort_key))
        scan_result = LibraryScanResult(
            root="/",
            accepted_paths=ordered_paths,
            skipped=(),
            errors=(),
            discovered_entries=len(ordered_paths),
            cancelled=not source_scan_complete,
        )
        return self.import_scan(scan_result)
