from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from data.models.analysis_record import AnalysisRecord
from data.models.canonical_analysis_record import (
    CanonicalAnalysisPersistenceRecord,
)

BPM_ABSOLUTE_TOLERANCE = 1.0
ENERGY_ABSOLUTE_TOLERANCE = 0.05
DURATION_SECONDS_TOLERANCE = 0.05
COMPARISON_SCHEMA_VERSION = "canonical-legacy-comparison-v1"


class FieldComparisonStatus(StrEnum):
    EXACT_MATCH = "exact_match"
    WITHIN_TOLERANCE = "within_tolerance"
    MISMATCH = "mismatch"
    MISSING_LEGACY = "missing_legacy"
    MISSING_CANONICAL = "missing_canonical"
    NOT_COMPARABLE = "not_comparable"


@dataclass(frozen=True, slots=True)
class FieldComparison:
    field: str
    status: FieldComparisonStatus
    legacy_value: str | float | None
    canonical_value: str | float | None
    absolute_delta: float | None = None


@dataclass(frozen=True, slots=True)
class CanonicalLegacyComparison:
    track_id: str
    provider: str
    legacy_analysis_version: str
    canonical_analysis_version: str
    comparison_schema_version: str
    fields: tuple[FieldComparison, ...]

    @property
    def mismatched_fields(self) -> tuple[str, ...]:
        mismatch_statuses = {
            FieldComparisonStatus.MISMATCH,
            FieldComparisonStatus.MISSING_LEGACY,
            FieldComparisonStatus.MISSING_CANONICAL,
        }
        return tuple(
            item.field
            for item in self.fields
            if item.status in mismatch_statuses
        )

    @property
    def matched_fields(self) -> tuple[str, ...]:
        match_statuses = {
            FieldComparisonStatus.EXACT_MATCH,
            FieldComparisonStatus.WITHIN_TOLERANCE,
        }
        return tuple(
            item.field
            for item in self.fields
            if item.status in match_statuses
        )

    @property
    def outcome(self) -> str:
        return "mismatch" if self.mismatched_fields else "succeeded"


_CAMELOT_TO_KEY = {
    "1A": "G# minor",
    "2A": "D# minor",
    "3A": "A# minor",
    "4A": "F minor",
    "5A": "C minor",
    "6A": "G minor",
    "7A": "D minor",
    "8A": "A minor",
    "9A": "E minor",
    "10A": "B minor",
    "11A": "F# minor",
    "12A": "C# minor",
    "1B": "B major",
    "2B": "F# major",
    "3B": "C# major",
    "4B": "G# major",
    "5B": "D# major",
    "6B": "A# major",
    "7B": "F major",
    "8B": "C major",
    "9B": "G major",
    "10B": "D major",
    "11B": "A major",
    "12B": "E major",
}

_NOTE_ALIASES = {
    "ab": "G#",
    "a#": "A#",
    "bb": "A#",
    "c#": "C#",
    "db": "C#",
    "d#": "D#",
    "eb": "D#",
    "f#": "F#",
    "gb": "F#",
    "g#": "G#",
}


def _normalize_note(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    first = stripped[0].upper()
    accidental = stripped[1:2]
    raw_note = first + accidental
    return _NOTE_ALIASES.get(raw_note.lower(), raw_note)


def normalize_key(
    key: str | None,
    *,
    scale: str | None = None,
    camelot: str | None = None,
) -> str | None:
    if camelot:
        mapped = _CAMELOT_TO_KEY.get(camelot.strip().upper())
        if mapped is not None:
            return mapped

    if key is None or not key.strip():
        return None

    value = key.strip()
    lowered = value.lower()
    inferred_scale = scale.strip().lower() if scale else None

    if lowered.endswith(" minor"):
        inferred_scale = "minor"
        value = value[:-6].strip()
    elif lowered.endswith(" major"):
        inferred_scale = "major"
        value = value[:-6].strip()
    elif lowered.endswith("min"):
        inferred_scale = "minor"
        value = value[:-3].strip()
    elif lowered.endswith("maj"):
        inferred_scale = "major"
        value = value[:-3].strip()
    elif lowered.endswith("m") and len(value) > 1:
        inferred_scale = "minor"
        value = value[:-1].strip()

    note = _normalize_note(value)
    if not note:
        return None

    mode = inferred_scale if inferred_scale in {"major", "minor"} else None
    return f"{note} {mode}" if mode else note


def _compare_numeric(
    field: str,
    legacy: float | None,
    canonical: float | None,
    tolerance: float,
) -> FieldComparison:
    if legacy is None and canonical is None:
        return FieldComparison(
            field=field,
            status=FieldComparisonStatus.NOT_COMPARABLE,
            legacy_value=None,
            canonical_value=None,
        )
    if legacy is None:
        return FieldComparison(
            field=field,
            status=FieldComparisonStatus.MISSING_LEGACY,
            legacy_value=None,
            canonical_value=canonical,
        )
    if canonical is None:
        return FieldComparison(
            field=field,
            status=FieldComparisonStatus.MISSING_CANONICAL,
            legacy_value=legacy,
            canonical_value=None,
        )

    delta = abs(float(legacy) - float(canonical))
    if delta == 0:
        status = FieldComparisonStatus.EXACT_MATCH
    elif delta <= tolerance:
        status = FieldComparisonStatus.WITHIN_TOLERANCE
    else:
        status = FieldComparisonStatus.MISMATCH

    return FieldComparison(
        field=field,
        status=status,
        legacy_value=legacy,
        canonical_value=canonical,
        absolute_delta=delta,
    )


def _compare_key(
    legacy: AnalysisRecord,
    canonical: CanonicalAnalysisPersistenceRecord,
) -> FieldComparison:
    legacy_key = normalize_key(
        legacy.key,
        scale=legacy.scale,
        camelot=legacy.camelot,
    )
    canonical_key = normalize_key(canonical.key)

    if legacy_key is None and canonical_key is None:
        status = FieldComparisonStatus.NOT_COMPARABLE
    elif legacy_key is None:
        status = FieldComparisonStatus.MISSING_LEGACY
    elif canonical_key is None:
        status = FieldComparisonStatus.MISSING_CANONICAL
    elif legacy_key == canonical_key:
        status = FieldComparisonStatus.EXACT_MATCH
    else:
        status = FieldComparisonStatus.MISMATCH

    return FieldComparison(
        field="key",
        status=status,
        legacy_value=legacy_key,
        canonical_value=canonical_key,
    )


def compare_canonical_to_legacy(
    legacy: AnalysisRecord,
    canonical: CanonicalAnalysisPersistenceRecord,
) -> CanonicalLegacyComparison:
    if legacy.track_id != canonical.track_id:
        raise ValueError("legacy and canonical track_id must match")

    fields = (
        _compare_numeric(
            "bpm",
            legacy.bpm,
            canonical.bpm,
            BPM_ABSOLUTE_TOLERANCE,
        ),
        _compare_numeric(
            "bpm_confidence",
            legacy.bpm_confidence,
            canonical.bpm_confidence,
            0.05,
        ),
        _compare_key(legacy, canonical),
        _compare_numeric(
            "energy",
            legacy.energy,
            canonical.energy,
            ENERGY_ABSOLUTE_TOLERANCE,
        ),
        _compare_numeric(
            "loudness_db",
            legacy.loudness_db,
            canonical.loudness_db,
            0.5,
        ),
        _compare_numeric(
            "duration_seconds",
            legacy.duration_seconds,
            canonical.duration_seconds,
            DURATION_SECONDS_TOLERANCE,
        ),
    )

    return CanonicalLegacyComparison(
        track_id=legacy.track_id,
        provider=canonical.provider,
        legacy_analysis_version=legacy.analysis_version,
        canonical_analysis_version=canonical.canonical_analysis_version,
        comparison_schema_version=COMPARISON_SCHEMA_VERSION,
        fields=fields,
    )
