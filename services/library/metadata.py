from __future__ import annotations

from collections.abc import Iterable
from importlib.metadata import PackageNotFoundError, version
import math
from pathlib import Path
from typing import Any, Protocol

from tinytag import TinyTag, TinyTagException

from core.library.track_metadata import MetadataOrigin, TrackMetadata


class MetadataReadError(RuntimeError):
    def __init__(self, *, path: str, code: str, detail: str) -> None:
        super().__init__(detail)
        self.path = path
        self.code = code
        self.detail = detail


class TrackMetadataReader(Protocol):
    def read(self, path: str | Path) -> TrackMetadata: ...


def _resolve_regular_file(path: str | Path) -> Path:
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
    return resolved


def _normalize_text(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    values: Iterable[Any]
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, (list, tuple, set, frozenset)):
        values = value
    else:
        raise TypeError(f"TinyTag {field_name} must be text or a text collection")

    normalized_values: list[str] = []
    for item in values:
        if item is None:
            continue
        if not isinstance(item, str):
            raise TypeError(f"TinyTag {field_name} values must be strings")
        normalized = " ".join(item.split())
        if normalized:
            normalized_values.append(normalized)

    if not normalized_values:
        return None
    if isinstance(value, (set, frozenset)):
        normalized_values.sort(key=lambda item: (item.casefold(), item))
    return "; ".join(dict.fromkeys(normalized_values))


def _positive_float(value: Any, *, field_name: str, warnings: list[str]) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        warnings.append(f"TinyTag {field_name} was non-numeric and was ignored")
        return None
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0:
        warnings.append(f"TinyTag {field_name} was non-positive or non-finite and was ignored")
        return None
    return normalized


def _positive_int(value: Any, *, field_name: str, warnings: list[str]) -> int | None:
    normalized = _positive_float(value, field_name=field_name, warnings=warnings)
    if normalized is None:
        return None
    return max(1, int(round(normalized)))


class FilenameFallbackMetadataReader:
    provider_name = "filename-fallback"
    provider_version = "1"

    def read(self, path: str | Path) -> TrackMetadata:
        resolved = _resolve_regular_file(path)
        title = " ".join(resolved.stem.replace("_", " ").split()) or None
        return TrackMetadata(
            source_path=str(resolved),
            provider=self.provider_name,
            provider_version=self.provider_version,
            origin=MetadataOrigin.FILENAME_FALLBACK,
            title=title,
            warnings=("tagged metadata not read; title derived from filename",),
        )


class TinyTagMetadataReader:
    provider_name = "tinytag"

    def __init__(self) -> None:
        try:
            self.provider_version = version("tinytag")
        except PackageNotFoundError:
            self.provider_version = "unknown"
        self._filename_fallback = FilenameFallbackMetadataReader()

    def read(self, path: str | Path) -> TrackMetadata:
        resolved = _resolve_regular_file(path)
        try:
            tag = TinyTag.get(str(resolved))
        except (TinyTagException, OSError, ValueError) as exc:
            raise MetadataReadError(
                path=str(resolved),
                code="metadata_parse_failed",
                detail="TinyTag could not parse the audio metadata",
            ) from exc

        warnings: list[str] = []
        try:
            title = _normalize_text(tag.title, field_name="title")
            artist = _normalize_text(tag.artist, field_name="artist")
            album = _normalize_text(tag.album, field_name="album")
            genre = _normalize_text(tag.genre, field_name="genre")
        except TypeError as exc:
            raise MetadataReadError(
                path=str(resolved),
                code="metadata_output_invalid",
                detail=str(exc),
            ) from exc

        origin = MetadataOrigin.TAGS
        if title is None:
            fallback = self._filename_fallback.read(resolved)
            title = fallback.title
            origin = MetadataOrigin.TAGS_WITH_FILENAME_FALLBACK
            warnings.append("title tag missing; title derived from filename")

        duration = _positive_float(
            getattr(tag, "duration", None),
            field_name="duration",
            warnings=warnings,
        )
        sample_rate = _positive_int(
            getattr(tag, "samplerate", None),
            field_name="sample rate",
            warnings=warnings,
        )
        bitrate = _positive_int(
            getattr(tag, "bitrate", None),
            field_name="bitrate",
            warnings=warnings,
        )

        if artist is None:
            warnings.append("artist tag missing")
        if album is None:
            warnings.append("album tag missing")
        if genre is None:
            warnings.append("genre tag missing")

        return TrackMetadata(
            source_path=str(resolved),
            provider=self.provider_name,
            provider_version=self.provider_version,
            origin=origin,
            title=title,
            artist=artist,
            album=album,
            genre=genre,
            duration_seconds=duration,
            sample_rate_hz=sample_rate,
            bitrate_kbps=bitrate,
            warnings=tuple(warnings),
        )
