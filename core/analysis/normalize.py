from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

try:
    from core.analysis.contracts import (
        AnalysisProvenance,
        CanonicalAnalysisResult,
        EnergyEstimate,
        KeyEstimate,
        TempoEstimate,
    )
except Exception:
    from dataclasses import dataclass, field
    from typing import Any, List, Dict

    @dataclass
    class TempoEstimate:
        bpm: float | None = None
        confidence: float | None = None

    @dataclass
    class KeyEstimate:
        value: str | None = None
        system: str = "camelot"
        confidence: float | None = None

    @dataclass
    class EnergyEstimate:
        value: float | None = None
        confidence: float | None = None

    @dataclass
    class AnalysisProvenance:
        provider: str
        provider_version: str | None = None
        analysis_version: str | None = None
        analyzed_at: str | None = None

    @dataclass
    class CanonicalAnalysisResult:
        track_id: str | None = None
        source_path: str = ""
        tempo: TempoEstimate = field(default_factory=TempoEstimate)
        key: KeyEstimate = field(default_factory=KeyEstimate)
        energy: EnergyEstimate = field(default_factory=EnergyEstimate)
        duration_seconds: float | None = None
        sample_rate_hz: int | None = None
        channels: int | None = None
        loudness_integrated_lufs: float | None = None
        provenance: AnalysisProvenance | None = None
        warnings: List[str] = field(default_factory=list)
        raw_provider_fields: Dict[str, Any] = field(default_factory=dict)


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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _essentia_key_to_camelot(key_value: str | None) -> str | None:
    if not key_value:
        return None
    return NOTE_TO_CAMELOT.get(key_value)


def normalize_provider_result(provider_name: str, payload: Dict[str, Any]) -> CanonicalAnalysisResult:
    provider = provider_name.strip().lower()

    source_path = payload.get("path") or payload.get("source_path") or ""
    warnings = list(payload.get("warnings", []))
    provider_version = payload.get("provider_version")

    bpm = payload.get("bpm")
    bpm_conf = payload.get("bpm_confidence")

    key_value = payload.get("key") or payload.get("camelot")
    key_system = payload.get("key_system", "camelot")
    key_conf = payload.get("key_confidence")

    energy_value = payload.get("energy")
    energy_conf = payload.get("energy_confidence")

    if provider == "librosa":
        bpm = bpm if bpm is not None else payload.get("tempo")
        if bpm_conf is None:
            bpm_conf = 0.5 if bpm is not None else None

    elif provider == "essentia":
        bpm = bpm if bpm is not None else payload.get("rhythm_bpm")
        if bpm_conf is None:
            bpm_conf = 0.8 if bpm is not None else None

        if key_value is None:
            raw_key = payload.get("key_key")
            key_value = _essentia_key_to_camelot(raw_key)
            if raw_key and key_value is None:
                warnings.append(f"unmapped Essentia key: {raw_key}")

        key_system = "camelot"
        if key_conf is None:
            key_conf = payload.get("key_strength")

        if energy_value is None:
            energy_value = payload.get("loudness_energy")
        if energy_conf is None:
            energy_conf = 0.7 if energy_value is not None else None

    elif provider == "mock":
        warnings.append("mock provider used for normalization test path")

    provenance = AnalysisProvenance(
        provider=provider,
        provider_version=provider_version,
        analysis_version="bundle26-essentia-v1",
        analyzed_at=payload.get("analyzed_at") or _utc_now_iso(),
    )

    return CanonicalAnalysisResult(
        track_id=payload.get("track_id"),
        source_path=source_path,
        tempo=TempoEstimate(bpm=bpm, confidence=bpm_conf),
        key=KeyEstimate(value=key_value, system=key_system, confidence=key_conf),
        energy=EnergyEstimate(value=energy_value, confidence=energy_conf),
        duration_seconds=payload.get("duration_seconds"),
        sample_rate_hz=payload.get("sample_rate_hz"),
        channels=payload.get("channels"),
        loudness_integrated_lufs=payload.get("loudness_integrated_lufs"),
        provenance=provenance,
        warnings=warnings,
        raw_provider_fields=dict(payload),
    )
