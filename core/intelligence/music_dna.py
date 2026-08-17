from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from core.analysis.provider_contract import CanonicalAnalysisResult
from core.analysis.rhythm_contracts import EvidenceStatus, RhythmicStructureAnalysis

MUSIC_DNA_CONTRACT_VERSION = "music-dna-v1"


class FactStatus(StrEnum):
    MEASURED = "measured"
    DERIVED = "derived"
    UNAVAILABLE = "unavailable"


class CalibrationState(StrEnum):
    UNKNOWN = "unknown"
    UNCALIBRATED = "uncalibrated"
    CALIBRATED = "calibrated"


@dataclass(frozen=True, slots=True)
class Confidence:
    score: float | None
    calibration_state: CalibrationState
    evidence_count: int
    disagreement: float | None = None

    def __post_init__(self) -> None:
        if self.score is not None and not 0.0 <= self.score <= 1.0:
            raise ValueError("confidence score must be between 0 and 1")
        if self.evidence_count < 1:
            raise ValueError("evidence_count must be at least one")
        if self.disagreement is not None and not 0.0 <= self.disagreement <= 1.0:
            raise ValueError("confidence disagreement must be between 0 and 1")
        if self.score is None and self.calibration_state is not CalibrationState.UNKNOWN:
            raise ValueError("unknown confidence score requires unknown calibration state")


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    evidence_id: str
    provider_id: str
    provider_version: str
    algorithm_or_model_version: str
    input_identity: str
    benchmark_status: str
    confidence: Confidence
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "evidence_id",
            "provider_id",
            "provider_version",
            "algorithm_or_model_version",
            "input_identity",
            "benchmark_status",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} must not be empty")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "warnings", tuple(str(item) for item in self.warnings))


@dataclass(frozen=True, slots=True)
class MusicDNAIdentity:
    track_id: str
    content_identity: str
    analysis_revision: str
    contract_version: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "track_id",
            "content_identity",
            "analysis_revision",
            "contract_version",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} must not be empty")
            object.__setattr__(self, field_name, value)
        refs = tuple(str(item).strip() for item in self.evidence_refs if str(item).strip())
        if not refs:
            raise ValueError("evidence_refs must not be empty")
        object.__setattr__(self, "evidence_refs", refs)


@dataclass(frozen=True, slots=True)
class TempoHypothesis:
    bpm: float
    relation_to_primary: str
    status: FactStatus
    confidence: Confidence

    def __post_init__(self) -> None:
        bpm = float(self.bpm)
        if not math.isfinite(bpm) or not 20.0 <= bpm <= 400.0:
            raise ValueError("tempo hypothesis BPM must be between 20 and 400")
        relation = self.relation_to_primary.strip()
        if not relation:
            raise ValueError("relation_to_primary must not be empty")
        object.__setattr__(self, "bpm", bpm)
        object.__setattr__(self, "relation_to_primary", relation)


@dataclass(frozen=True, slots=True)
class RhythmDNA:
    dominant_bpm: float | None
    bpm_hypotheses: tuple[TempoHypothesis, ...]
    beat_stability: float | None
    percussive_ratio: float | None
    timing_status: FactStatus
    phrase_boundaries_seconds: tuple[float, ...]
    confidence: Confidence

    def __post_init__(self) -> None:
        if self.dominant_bpm is not None:
            bpm = float(self.dominant_bpm)
            if not math.isfinite(bpm) or not 20.0 <= bpm <= 400.0:
                raise ValueError("dominant_bpm must be between 20 and 400")
            object.__setattr__(self, "dominant_bpm", bpm)
        for field_name in ("beat_stability", "percussive_ratio"):
            value = getattr(self, field_name)
            if value is not None and not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{field_name} must be between 0 and 1")
        boundaries = tuple(float(item) for item in self.phrase_boundaries_seconds)
        if any(not math.isfinite(item) or item < 0.0 for item in boundaries):
            raise ValueError("phrase boundaries must be finite and non-negative")
        if any(current <= previous for previous, current in zip(boundaries, boundaries[1:])):
            raise ValueError("phrase boundaries must be strictly increasing")
        object.__setattr__(self, "phrase_boundaries_seconds", boundaries)
        object.__setattr__(self, "bpm_hypotheses", tuple(self.bpm_hypotheses))


@dataclass(frozen=True, slots=True)
class TonalDNA:
    global_key: str | None
    key_tonic: str | None
    key_scale: str | None
    camelot: str | None
    confidence: Confidence
    status: FactStatus


@dataclass(frozen=True, slots=True)
class EnergyVector:
    baseline_energy: float | None
    perceived_loudness_db: float | None
    harmonic_ratio: float | None
    percussive_ratio: float | None
    projection_version: str
    confidence: Confidence

    def __post_init__(self) -> None:
        for field_name in ("baseline_energy", "harmonic_ratio", "percussive_ratio"):
            value = getattr(self, field_name)
            if value is not None and not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{field_name} must be between 0 and 1")
        if self.perceived_loudness_db is not None and not math.isfinite(
            float(self.perceived_loudness_db)
        ):
            raise ValueError("perceived_loudness_db must be finite")
        if not self.projection_version.strip():
            raise ValueError("projection_version must not be empty")


@dataclass(frozen=True, slots=True)
class MusicSegmentDNA:
    segment_id: str
    start_seconds: float
    end_seconds: float
    structural_label: str
    status: FactStatus
    confidence: Confidence
    evidence_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.segment_id.strip():
            raise ValueError("segment_id must not be empty")
        start = float(self.start_seconds)
        end = float(self.end_seconds)
        if not math.isfinite(start) or not math.isfinite(end) or start < 0.0 or end <= start:
            raise ValueError("segment bounds must be finite with 0 <= start < end")
        label = self.structural_label.strip().lower()
        if not label:
            raise ValueError("structural_label must not be empty")
        object.__setattr__(self, "start_seconds", start)
        object.__setattr__(self, "end_seconds", end)
        object.__setattr__(self, "structural_label", label)
        object.__setattr__(self, "evidence_codes", tuple(self.evidence_codes))


@dataclass(frozen=True, slots=True)
class MusicDNARevision:
    identity: MusicDNAIdentity
    duration_seconds: float
    rhythm: RhythmDNA
    tonal: TonalDNA
    energy: EnergyVector
    segments: tuple[MusicSegmentDNA, ...]
    evidence: tuple[EvidenceRef, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        duration = float(self.duration_seconds)
        if not math.isfinite(duration) or duration <= 0.0:
            raise ValueError("duration_seconds must be finite and greater than zero")
        segments = tuple(self.segments)
        if not segments:
            raise ValueError("Music DNA requires at least one bounded segment")
        if any(segment.end_seconds > duration for segment in segments):
            raise ValueError("Music DNA segment exceeds track duration")
        evidence = tuple(self.evidence)
        evidence_ids = {item.evidence_id for item in evidence}
        if set(self.identity.evidence_refs) - evidence_ids:
            raise ValueError("identity evidence_refs must resolve to Music DNA evidence")
        object.__setattr__(self, "duration_seconds", duration)
        object.__setattr__(self, "segments", segments)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "warnings", tuple(str(item) for item in self.warnings))

    def segment(self, segment_id: str) -> MusicSegmentDNA:
        for item in self.segments:
            if item.segment_id == segment_id:
                return item
        raise KeyError("unknown Music DNA segment")


def _confidence(score: float | None) -> Confidence:
    return Confidence(
        score=score,
        calibration_state=(
            CalibrationState.UNKNOWN if score is None else CalibrationState.UNCALIBRATED
        ),
        evidence_count=1,
    )


def _tempo_hypotheses(bpm: float | None, confidence: Confidence) -> tuple[TempoHypothesis, ...]:
    if bpm is None:
        return ()
    candidates = [(bpm, "primary", FactStatus.MEASURED)]
    if bpm / 2.0 >= 20.0:
        candidates.append((bpm / 2.0, "half_time", FactStatus.DERIVED))
    if bpm * 2.0 <= 400.0:
        candidates.append((bpm * 2.0, "double_time", FactStatus.DERIVED))
    return tuple(
        TempoHypothesis(
            bpm=value,
            relation_to_primary=relation,
            status=status,
            confidence=confidence,
        )
        for value, relation, status in candidates
    )


def _timing_status(rhythm: RhythmicStructureAnalysis | None) -> FactStatus:
    if rhythm is None or rhythm.beat_grid.status is EvidenceStatus.UNAVAILABLE:
        return FactStatus.UNAVAILABLE
    if rhythm.beat_grid.status is EvidenceStatus.MEASURED:
        return FactStatus.MEASURED
    return FactStatus.DERIVED


def _segments(
    track_id: str,
    duration_seconds: float,
    rhythm: RhythmicStructureAnalysis | None,
) -> tuple[MusicSegmentDNA, ...]:
    if rhythm is not None and rhythm.segments:
        return tuple(
            MusicSegmentDNA(
                segment_id=f"{track_id}:segment:{index}",
                start_seconds=item.start_seconds,
                end_seconds=item.end_seconds,
                structural_label=item.label.value,
                status=FactStatus.DERIVED,
                confidence=_confidence(item.confidence),
                evidence_codes=item.evidence_codes,
            )
            for index, item in enumerate(rhythm.segments)
        )
    return (
        MusicSegmentDNA(
            segment_id=f"{track_id}:whole",
            start_seconds=0.0,
            end_seconds=duration_seconds,
            structural_label="unknown",
            status=FactStatus.DERIVED,
            confidence=_confidence(None),
            evidence_codes=("whole_track_fallback",),
        ),
    )


def build_music_dna(
    *,
    track_id: str,
    content_identity: str,
    analysis_revision: str,
    evidence_id: str,
    input_identity: str,
    canonical: CanonicalAnalysisResult,
    rhythmic_structure: RhythmicStructureAnalysis | None = None,
    benchmark_status: str = "unknown",
) -> MusicDNARevision:
    """Build a path-free Music DNA revision from already normalized analysis evidence."""
    if canonical.duration_seconds is None or canonical.duration_seconds <= 0.0:
        raise ValueError("Music DNA requires positive canonical duration evidence")
    if canonical.provider_version is None or canonical.algorithm_version is None:
        raise ValueError("Music DNA requires explicit provider and algorithm versions")
    if rhythmic_structure is not None:
        if rhythmic_structure.track_id != track_id:
            raise ValueError("rhythmic structure track_id must match Music DNA track_id")
        if abs(rhythmic_structure.duration_seconds - canonical.duration_seconds) > 0.001:
            raise ValueError("rhythmic structure duration must match canonical duration")

    provider_confidence_scores = tuple(
        value
        for value in (canonical.bpm_confidence, canonical.key_confidence)
        if value is not None
    )
    provider_confidence = (
        min(provider_confidence_scores) if provider_confidence_scores else None
    )
    evidence_confidence = _confidence(provider_confidence)
    evidence = EvidenceRef(
        evidence_id=evidence_id,
        provider_id=canonical.provider,
        provider_version=canonical.provider_version,
        algorithm_or_model_version=canonical.algorithm_version,
        input_identity=input_identity,
        benchmark_status=benchmark_status,
        confidence=evidence_confidence,
        warnings=canonical.warnings,
    )
    identity = MusicDNAIdentity(
        track_id=track_id,
        content_identity=content_identity,
        analysis_revision=analysis_revision,
        contract_version=MUSIC_DNA_CONTRACT_VERSION,
        evidence_refs=(evidence_id,),
    )
    rhythm_confidence = _confidence(canonical.bpm_confidence)
    rhythm = RhythmDNA(
        dominant_bpm=canonical.bpm,
        bpm_hypotheses=_tempo_hypotheses(canonical.bpm, rhythm_confidence),
        beat_stability=canonical.beat_stability,
        percussive_ratio=canonical.percussive_ratio,
        timing_status=_timing_status(rhythmic_structure),
        phrase_boundaries_seconds=(
            tuple(item.time_seconds for item in rhythmic_structure.phrase_boundaries)
            if rhythmic_structure is not None
            else ()
        ),
        confidence=rhythm_confidence,
    )
    tonal = TonalDNA(
        global_key=canonical.key,
        key_tonic=canonical.key_tonic,
        key_scale=canonical.key_scale,
        camelot=canonical.camelot,
        confidence=_confidence(canonical.key_confidence),
        status=(FactStatus.MEASURED if canonical.key is not None else FactStatus.UNAVAILABLE),
    )
    energy = EnergyVector(
        baseline_energy=canonical.energy,
        perceived_loudness_db=canonical.loudness_db,
        harmonic_ratio=canonical.harmonic_ratio,
        percussive_ratio=canonical.percussive_ratio,
        projection_version="baseline-energy-v1",
        confidence=_confidence(None),
    )
    return MusicDNARevision(
        identity=identity,
        duration_seconds=canonical.duration_seconds,
        rhythm=rhythm,
        tonal=tonal,
        energy=energy,
        segments=_segments(track_id, canonical.duration_seconds, rhythmic_structure),
        evidence=(evidence,),
        warnings=canonical.warnings,
    )


__all__ = [
    "CalibrationState",
    "Confidence",
    "EnergyVector",
    "EvidenceRef",
    "FactStatus",
    "MUSIC_DNA_CONTRACT_VERSION",
    "MusicDNAIdentity",
    "MusicDNARevision",
    "MusicSegmentDNA",
    "RhythmDNA",
    "TempoHypothesis",
    "TonalDNA",
    "build_music_dna",
]
