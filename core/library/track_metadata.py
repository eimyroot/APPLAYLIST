from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MetadataOrigin(str, Enum):
    TAGS = "tags"
    FILENAME_FALLBACK = "filename_fallback"


@dataclass(frozen=True, slots=True)
class TrackIdentity:
    track_id: str
    digest_algorithm: str
    digest_hex: str
    source_path: str
    size_bytes: int
    mtime_ns: int

    def __post_init__(self) -> None:
        if self.digest_algorithm != "sha256":
            raise ValueError("track identity digest algorithm must be sha256")
        if not _SHA256_RE.fullmatch(self.digest_hex):
            raise ValueError("track identity digest must be lowercase sha256 hex")
        expected_track_id = f"aptrack:v1:sha256:{self.digest_hex}"
        if self.track_id != expected_track_id:
            raise ValueError("track id does not match the content digest")
        if not Path(self.source_path).is_absolute():
            raise ValueError("track identity source path must be absolute")
        if not isinstance(self.size_bytes, int) or isinstance(self.size_bytes, bool):
            raise TypeError("track identity size must be an integer")
        if self.size_bytes < 0:
            raise ValueError("track identity size must be non-negative")
        if not isinstance(self.mtime_ns, int) or isinstance(self.mtime_ns, bool):
            raise TypeError("track identity mtime must be an integer")
        if self.mtime_ns < 0:
            raise ValueError("track identity mtime must be non-negative")


@dataclass(frozen=True, slots=True)
class TrackMetadata:
    source_path: str
    provider: str
    provider_version: str
    origin: MetadataOrigin
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    genre: str | None = None
    duration_seconds: float | None = None
    sample_rate_hz: int | None = None
    bitrate_kbps: int | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not Path(self.source_path).is_absolute():
            raise ValueError("metadata source path must be absolute")
        if not isinstance(self.provider, str):
            raise TypeError("metadata provider must be a string")
        if not self.provider.strip():
            raise ValueError("metadata provider is required")
        if not isinstance(self.provider_version, str):
            raise TypeError("metadata provider version must be a string")
        if not self.provider_version.strip():
            raise ValueError("metadata provider version is required")

        object.__setattr__(self, "provider", self.provider.strip())
        object.__setattr__(self, "provider_version", self.provider_version.strip())

        origin = self.origin
        if not isinstance(origin, MetadataOrigin):
            try:
                origin = MetadataOrigin(origin)
            except (TypeError, ValueError) as exc:
                raise ValueError("unsupported metadata origin") from exc
            object.__setattr__(self, "origin", origin)

        for field_name in ("title", "artist", "album", "genre"):
            value = getattr(self, field_name)
            if value is not None:
                if not isinstance(value, str):
                    raise TypeError(f"{field_name} must be a string")
                normalized = " ".join(value.split())
                object.__setattr__(self, field_name, normalized or None)

        if self.duration_seconds is not None:
            if isinstance(self.duration_seconds, bool) or not isinstance(
                self.duration_seconds,
                (int, float),
            ):
                raise TypeError("duration must be numeric")
            duration = float(self.duration_seconds)
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("duration must be finite and positive")
            object.__setattr__(self, "duration_seconds", duration)

        for field_name in ("sample_rate_hz", "bitrate_kbps"):
            value = getattr(self, field_name)
            if value is not None:
                if not isinstance(value, int) or isinstance(value, bool):
                    raise TypeError(f"{field_name} must be an integer")
                if value <= 0:
                    raise ValueError(f"{field_name} must be positive")

        normalized_warning_values: set[str] = set()
        for value in self.warnings:
            if not isinstance(value, str):
                raise TypeError("metadata warnings must be strings")
            normalized = " ".join(value.split())
            if normalized:
                normalized_warning_values.add(normalized)
        normalized_warnings = tuple(
            sorted(
                normalized_warning_values,
                key=lambda value: (value.casefold(), value),
            )
        )
        object.__setattr__(self, "warnings", normalized_warnings)


@dataclass(frozen=True, slots=True)
class TrackImportCandidate:
    identity: TrackIdentity
    metadata: TrackMetadata

    def __post_init__(self) -> None:
        if self.identity.source_path != self.metadata.source_path:
            raise ValueError("identity and metadata source paths must match")


@dataclass(frozen=True, slots=True)
class TrackImportIssue:
    path: str
    code: str
    detail: str

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("import issue path is required")
        if not self.code:
            raise ValueError("import issue code is required")
        if not self.detail:
            raise ValueError("import issue detail is required")


@dataclass(frozen=True, slots=True)
class TrackImportBatchResult:
    candidates: tuple[TrackImportCandidate, ...]
    issues: tuple[TrackImportIssue, ...]
    source_scan_complete: bool

    def __post_init__(self) -> None:
        if not isinstance(self.source_scan_complete, bool):
            raise TypeError("source_scan_complete must be boolean")
        track_ids = tuple(candidate.identity.track_id for candidate in self.candidates)
        if len(set(track_ids)) != len(track_ids):
            raise ValueError("import candidates must have unique track ids")
        paths = tuple(candidate.identity.source_path for candidate in self.candidates)
        expected = tuple(sorted(paths, key=lambda value: (value.casefold(), value)))
        if paths != expected:
            raise ValueError("import candidates must be deterministically sorted")
