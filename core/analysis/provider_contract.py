from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping


class ProviderContractError(Exception):
    """Base class for controlled provider failures."""

    code = "provider_error"

    def __init__(self, message: str, *, provider: str | None = None) -> None:
        super().__init__(message)
        self.provider = provider


class UnknownProviderError(ProviderContractError, ValueError):
    code = "provider_unknown"


class ProviderUnavailableError(ProviderContractError, RuntimeError):
    code = "provider_unavailable"


class ProviderRuntimeFailure(ProviderContractError, RuntimeError):
    code = "provider_runtime_error"


class ProviderOutputInvalid(ProviderContractError, ValueError):
    code = "provider_output_invalid"


@dataclass(frozen=True, slots=True)
class CanonicalAnalysisResult:
    path: str
    provider: str
    bpm: float | None
    bpm_confidence: float | None
    key: str | None
    key_confidence: float | None
    energy: float | None
    loudness_db: float | None
    duration_seconds: float | None
    genre_hint: str | None
    analysis_status: str = "ok"
    analysis_version: str = "canonical-mir-v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_mapping(value: Any, field: str, provider: str | None) -> Mapping[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return value
    raise ProviderOutputInvalid(
        f"Provider field '{field}' must be an object",
        provider=provider,
    )


def _as_optional_float(value: Any, field: str, provider: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ProviderOutputInvalid(
            f"Provider field '{field}' must be numeric",
            provider=provider,
        )
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ProviderOutputInvalid(
            f"Provider field '{field}' must be numeric",
            provider=provider,
        ) from exc
    if not math.isfinite(parsed):
        raise ProviderOutputInvalid(
            f"Provider field '{field}' must be finite",
            provider=provider,
        )
    return parsed


def _bounded(
    value: float | None,
    field: str,
    provider: str,
    *,
    minimum: float,
    maximum: float,
) -> float | None:
    if value is not None and not minimum <= value <= maximum:
        raise ProviderOutputInvalid(
            f"Provider field '{field}' must be between {minimum} and {maximum}",
            provider=provider,
        )
    return value


def _optional_text(value: Any, field: str, provider: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProviderOutputInvalid(
            f"Provider field '{field}' must be text",
            provider=provider,
        )
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 128:
        raise ProviderOutputInvalid(
            f"Provider field '{field}' is too long",
            provider=provider,
        )
    return normalized


def normalize_provider_result(
    raw_result: Mapping[str, Any],
    *,
    path: str,
    expected_provider: str | None = None,
) -> CanonicalAnalysisResult:
    """Normalize a raw provider payload and reject unsafe or incomplete results."""
    if not isinstance(raw_result, Mapping):
        raise ProviderOutputInvalid("Provider result must be an object")
    if not isinstance(path, str) or not path.strip():
        raise ProviderOutputInvalid("Analysis path must be a non-empty string")

    raw_provider = raw_result.get("provider", expected_provider)
    if not isinstance(raw_provider, str) or not raw_provider.strip():
        raise ProviderOutputInvalid("Provider result must identify its provider")
    provider = raw_provider.strip().lower()

    if expected_provider and provider != expected_provider.strip().lower():
        raise ProviderOutputInvalid(
            "Provider result identity does not match the selected provider",
            provider=provider,
        )

    raw_status = raw_result.get("status")
    if not isinstance(raw_status, str):
        raise ProviderOutputInvalid(
            "Provider result must include a string status",
            provider=provider,
        )
    status = raw_status.strip().lower()
    if status not in {"ok", "success", "completed"}:
        raise ProviderOutputInvalid(
            f"Provider returned non-success status '{status or 'empty'}'",
            provider=provider,
        )

    beat = _as_mapping(raw_result.get("beat"), "beat", provider)
    metrics = _as_mapping(raw_result.get("metrics"), "metrics", provider)
    tags = _as_mapping(raw_result.get("tags"), "tags", provider)

    raw_key = raw_result.get("key")
    key_block = _as_mapping(raw_key, "key", provider) if not isinstance(raw_key, str) else {}

    bpm_raw = raw_result.get("bpm", beat.get("bpm"))
    bpm_confidence_raw = raw_result.get(
        "bpm_confidence",
        beat.get("confidence"),
    )

    if isinstance(raw_key, Mapping):
        key_raw = raw_key.get("camelot") or raw_key.get("key")
    else:
        key_raw = raw_key
    key_confidence_raw = raw_result.get(
        "key_confidence",
        key_block.get("confidence"),
    )

    energy_raw = raw_result.get("energy", metrics.get("energy_score"))
    loudness_raw = raw_result.get("loudness_db", metrics.get("loudness_db"))
    duration_raw = raw_result.get("duration_seconds")
    if duration_raw is None:
        duration_raw = raw_result.get("duration_sec", metrics.get("duration_seconds"))
    genre_raw = raw_result.get(
        "genre_hint",
        tags.get("primary_genre_hint", raw_result.get("genre")),
    )

    bpm = _bounded(
        _as_optional_float(bpm_raw, "bpm", provider),
        "bpm",
        provider,
        minimum=20.0,
        maximum=400.0,
    )
    bpm_confidence = _bounded(
        _as_optional_float(bpm_confidence_raw, "bpm_confidence", provider),
        "bpm_confidence",
        provider,
        minimum=0.0,
        maximum=1.0,
    )
    key_confidence = _bounded(
        _as_optional_float(key_confidence_raw, "key_confidence", provider),
        "key_confidence",
        provider,
        minimum=0.0,
        maximum=1.0,
    )
    energy = _bounded(
        _as_optional_float(energy_raw, "energy", provider),
        "energy",
        provider,
        minimum=0.0,
        maximum=1.0,
    )
    duration_seconds = _as_optional_float(
        duration_raw,
        "duration_seconds",
        provider,
    )
    if duration_seconds is not None and duration_seconds < 0:
        raise ProviderOutputInvalid(
            "Provider field 'duration_seconds' must not be negative",
            provider=provider,
        )

    return CanonicalAnalysisResult(
        path=path.strip(),
        provider=provider,
        bpm=bpm,
        bpm_confidence=bpm_confidence,
        key=_optional_text(key_raw, "key", provider),
        key_confidence=key_confidence,
        energy=energy,
        loudness_db=_as_optional_float(loudness_raw, "loudness_db", provider),
        duration_seconds=duration_seconds,
        genre_hint=_optional_text(genre_raw, "genre_hint", provider),
    )
