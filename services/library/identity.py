from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from core.library.track_metadata import TrackIdentity


@dataclass(frozen=True, slots=True)
class TrackIdentityError(Exception):
    path: str
    code: str
    detail: str

    def __str__(self) -> str:
        return self.detail


class ContentTrackIdentityService:
    def __init__(self, *, chunk_size: int = 1024 * 1024) -> None:
        if not isinstance(chunk_size, int) or isinstance(chunk_size, bool):
            raise TypeError("chunk_size must be an integer")
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self._chunk_size = chunk_size

    def identify(self, path: str | Path) -> TrackIdentity:
        source = Path(path)
        if not source.is_absolute():
            raise TrackIdentityError(
                path=str(source),
                code="identity_path_not_absolute",
                detail="track identity requires an absolute path",
            )

        try:
            resolved = source.resolve(strict=True)
        except FileNotFoundError as exc:
            raise TrackIdentityError(
                path=str(source),
                code="identity_file_missing",
                detail="track identity source file does not exist",
            ) from exc
        except OSError as exc:
            raise TrackIdentityError(
                path=str(source),
                code="identity_path_unreadable",
                detail="track identity source path cannot be resolved",
            ) from exc

        if not resolved.is_file():
            raise TrackIdentityError(
                path=str(resolved),
                code="identity_not_regular_file",
                detail="track identity source must be a regular file",
            )

        try:
            before = resolved.stat()
            digest = hashlib.sha256()
            with resolved.open("rb") as handle:
                while True:
                    chunk = handle.read(self._chunk_size)
                    if not chunk:
                        break
                    digest.update(chunk)
            after = resolved.stat()
        except OSError as exc:
            raise TrackIdentityError(
                path=str(resolved),
                code="identity_read_failed",
                detail="track identity source could not be read",
            ) from exc

        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise TrackIdentityError(
                path=str(resolved),
                code="identity_file_changed",
                detail="track identity source changed while it was being read",
            )

        digest_hex = digest.hexdigest()
        return TrackIdentity(
            track_id=f"aptrack:v1:sha256:{digest_hex}",
            digest_algorithm="sha256",
            digest_hex=digest_hex,
            source_path=str(resolved),
            size_bytes=after.st_size,
            mtime_ns=after.st_mtime_ns,
        )
