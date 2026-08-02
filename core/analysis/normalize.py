from __future__ import annotations

from typing import Any

from core.analysis.contracts import CanonicalAnalysisResult

NOTE_TO_CAMELOT = {
    "C major": "8B",
    "A minor": "8A",
    "G major": "9B",
    "E minor": "9A",
    "D major": "10B",
    "B minor": "10A",
    "A major": "11B",
    "F# minor": "11A",
    "E major": "12B",
    "C# minor": "12A",
    "B major": "1B",
    "G# minor": "1A",
    "F# major": "2B",
    "D# minor": "2A",
    "C# major": "3B",
    "A# minor": "3A",
    "G# major": "4B",
    "F minor": "4A",
    "D# major": "5B",
    "C minor": "5A",
    "A# major": "6B",
    "G minor": "6A",
    "F major": "7B",
    "D minor": "7A",
}


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _essentia_key_to_camelot(key_value: str | None) -> str | None:
    if not key_value:
        return None
    return NOTE_TO_CAMELOT.get(key_value)


def normalize_provider_result(
    provider_name: str,
    payload: dict[str, Any],
) -> CanonicalAnalysisResult:
    provider = provider_name.strip().lower()

    source_path = payload.get("path") or payload.get("source_path") or ""
    warnings = list(payload.get("warnings", []))
    provider_version = payload.get("provider_version")

    bpm = payload.get("bpm")
    bpm_confidence = payload.get("bpm_confidence")

    key_value = payload.get("key") or payload.get("camelot")
    key_system = payload.get("key_system", "camelot")
    key_confidence = payload.get("key_confidence")

    energy = payload.get("energy")
    energy_confidence = payload.get("energy_confidence")

    if provider == "librosa":
        bpm = bpm if bpm is not None else payload.get("tempo")

    elif provider == "essentia":
        bpm = bpm if bpm is not None else payload.get("rhythm_bpm")
        if key_value is None:
            raw_key = payload.get("key_key")
            key_value = _essentia_key_to_camelot(_optional_str(raw_key))
            if raw_key and key_value is None:
                warnings.append(f"unmapped Essentia key: {raw_key}")
        key_system = "camelot"
        if energy is None:
            energy = payload.get("loudness_energy")

    elif provider == "mock":
        warnings.append("mock provider used for normalization test path")

    status = payload.get("status") or payload.get("analysis_status") or "unknown"
    genre_hint = payload.get("genre_hint") or payload.get("genre")

    return CanonicalAnalysisResult(
        track_id=_optional_str(payload.get("track_id")),
        path=str(source_path),
        provider=provider,
        bpm=_as_float(bpm),
        bpm_confidence=_as_float(bpm_confidence),
        key=key_value if isinstance(key_value, str) else None,
        key_confidence=_as_float(key_confidence),
        key_system=key_system if isinstance(key_system, str) else None,
        energy=_as_float(energy),
        energy_confidence=_as_float(energy_confidence),
        loudness_db=_as_float(payload.get("loudness_db")),
        loudness_integrated_lufs=_as_float(payload.get("loudness_integrated_lufs")),
        duration_seconds=_as_float(payload.get("duration_seconds")),
        sample_rate_hz=_as_int(payload.get("sample_rate_hz")),
        channels=_as_int(payload.get("channels")),
        genre_hint=genre_hint if isinstance(genre_hint, str) else None,
        analysis_status=str(status),
        source_analysis_version=_optional_str(payload.get("analysis_version")),
        provider_version=_optional_str(provider_version),
        analyzed_at=_optional_str(payload.get("analyzed_at")),
        warnings=tuple(str(item) for item in warnings),
        raw_provider_fields=dict(payload),
    )
