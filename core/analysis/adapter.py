from __future__ import annotations

from typing import Any

from core.analysis.contracts import CanonicalAnalysisResult
from core.analysis.providers import select_best_provider


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def canonicalize_provider_result(
    result: dict[str, Any],
    path: str,
) -> CanonicalAnalysisResult:
    provider = result.get("provider", "unknown")
    status = result.get("status", "unknown")

    beat = result.get("beat", {}) or {}
    key_block = result.get("key", {}) or {}
    metrics = result.get("metrics", {}) or {}
    tags = result.get("tags", {}) or {}

    bpm = result.get("bpm")
    if bpm is None:
        bpm = beat.get("bpm")

    bpm_confidence = result.get("bpm_confidence")
    if bpm_confidence is None:
        bpm_confidence = beat.get("confidence")

    key = result.get("key")
    if isinstance(key, dict):
        key = key.get("camelot") or key.get("key")
    elif key is None:
        key = key_block.get("camelot") or key_block.get("key")

    key_confidence = result.get("key_confidence")
    if key_confidence is None:
        key_confidence = key_block.get("confidence")

    energy = result.get("energy")
    if energy is None:
        energy = metrics.get("energy_score")

    energy_confidence = result.get("energy_confidence")
    if energy_confidence is None:
        energy_confidence = metrics.get("energy_confidence")

    loudness_db = result.get("loudness_db")
    if loudness_db is None:
        loudness_db = metrics.get("loudness_db")

    duration_seconds = result.get("duration_seconds")
    if duration_seconds is None:
        duration_seconds = result.get("duration_sec")
    if duration_seconds is None:
        duration_seconds = metrics.get("duration_seconds")

    genre_hint = result.get("genre_hint")
    if genre_hint is None:
        genre_hint = tags.get("primary_genre_hint") or result.get("genre")

    warnings = result.get("warnings", ())
    if not isinstance(warnings, (list, tuple)):
        warnings = (str(warnings),)

    sample_rate_hz = result.get("sample_rate_hz")
    channels = result.get("channels")

    return CanonicalAnalysisResult(
        path=path,
        provider=str(provider),
        bpm=_as_float(bpm),
        bpm_confidence=_as_float(bpm_confidence),
        key=key if isinstance(key, str) else None,
        key_confidence=_as_float(key_confidence),
        key_system=_optional_str(result.get("key_system")),
        energy=_as_float(energy),
        energy_confidence=_as_float(energy_confidence),
        loudness_db=_as_float(loudness_db),
        loudness_integrated_lufs=_as_float(result.get("loudness_integrated_lufs")),
        duration_seconds=_as_float(duration_seconds),
        sample_rate_hz=sample_rate_hz if isinstance(sample_rate_hz, int) else None,
        channels=channels if isinstance(channels, int) else None,
        genre_hint=genre_hint if isinstance(genre_hint, str) else None,
        analysis_status=str(status),
        source_analysis_version=_optional_str(result.get("analysis_version")),
        provider_version=_optional_str(result.get("provider_version")),
        analyzed_at=_optional_str(result.get("analyzed_at")),
        track_id=_optional_str(result.get("track_id")),
        warnings=tuple(str(item) for item in warnings),
        raw_provider_fields=dict(result),
    )


class CanonicalAnalysisService:
    def __init__(self, preferred_provider: str | None = None) -> None:
        self.provider = select_best_provider(preferred_provider)

    def analyze_path(self, path: str) -> CanonicalAnalysisResult:
        raw = self.provider.analyze(path)
        return canonicalize_provider_result(raw, path=path)
