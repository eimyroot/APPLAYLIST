from __future__ import annotations

from pathlib import Path
from typing import Protocol

from core.library.track_metadata import MetadataOrigin, TrackMetadata


class MetadataReadError(RuntimeError):
    def __init__(self, *, path: str, code: str, detail: str) -> None:
        super().__init__(detail)
        self.path = path
        self.code = code
        self.detail = detail


class TrackMetadataReader(Protocol):
    def read(self, path: str | Path) -> TrackMetadata: ...


class FilenameFallbackMetadataReader:
    provider_name = "filename-fallback"
    provider_version = "1"

    def read(self, path: str | Path) -> TrackMetadata:
        source = Path(path)
        if not source.is_absolute():
            raise MetadataReadError(
                path=str(source),
                code="metadata_path_not_absolute",
                detail="metadata reader requires an absolute path",
            )

        try:
            resolved = source.resolve(strict=True)
        except FileNotFoundError as exc:
            raise MetadataReadError(
                path=str(source),
                code="metadata_file_missing",
                detail="metadata source file does not exist",
            ) from exc
        except OSError as exc:
            raise MetadataReadError(
                path=str(source),
                code="metadata_path_unreadable",
                detail="metadata source path cannot be resolved",
            ) from exc

        if not resolved.is_file():
            raise MetadataReadError(
                path=str(resolved),
                code="metadata_not_regular_file",
                detail="metadata source must be a regular file",
            )

        title = " ".join(resolved.stem.replace("_", " ").split()) or None
        return TrackMetadata(
            source_path=str(resolved),
            provider=self.provider_name,
            provider_version=self.provider_version,
            origin=MetadataOrigin.FILENAME_FALLBACK,
            title=title,
            warnings=("tagged metadata not read; title derived from filename",),
        )
