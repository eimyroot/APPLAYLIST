from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from core.analysis.rhythm_contracts import (
    BeatEvent,
    BeatGrid,
    EvidenceProvenance,
    EvidenceStatus,
    RhythmicStructureAnalysis,
)
from core.analysis.rhythm_reconciliation import (
    WB006C_SHADOW_METHOD,
    CanonicalTempoEvidence,
)


class LibrosaBeatGridShadowAnalyzer:
    """Explicit-only, read-only beat-grid candidate with zero runtime registration."""

    provider_name = "librosa-shadow"
    algorithm_version = "wb006c-librosa-beat-grid-v1"
    shadow_method = WB006C_SHADOW_METHOD
    sample_rate = 22_050
    hop_length = 512

    def analyze(
        self,
        path: str,
        *,
        canonical_evidence: CanonicalTempoEvidence,
        track_id: str,
    ) -> RhythmicStructureAnalysis:
        source = self._validated_source(path)
        if canonical_evidence.track_id != track_id:
            raise ValueError("canonical track_id does not match requested track_id")

        import librosa
        import numpy as np

        waveform, sample_rate = librosa.load(
            str(source),
            sr=self.sample_rate,
            mono=True,
            dtype=np.float32,
        )
        waveform = np.asarray(waveform, dtype=np.float32)
        if waveform.ndim != 1 or waveform.size == 0:
            raise ValueError("decoded audio is empty or not mono")
        if not np.all(np.isfinite(waveform)):
            raise ValueError("decoded audio contains non-finite samples")

        duration = float(librosa.get_duration(y=waveform, sr=sample_rate))
        if not math.isfinite(duration) or duration <= 0.0:
            raise ValueError("decoded audio has invalid duration")
        self._validate_duration_binding(duration, canonical_evidence.duration_seconds)

        provenance = EvidenceProvenance(
            provider=self.provider_name,
            provider_version=str(librosa.__version__),
            algorithm_version=self.algorithm_version,
            method=self.shadow_method,
            source_analysis_version=canonical_evidence.source_analysis_version,
        )
        if float(np.max(np.abs(waveform))) < 1e-7:
            return self._unavailable(
                track_id=track_id,
                duration=duration,
                provenance=provenance,
                reason="SILENT_AUDIO",
            )

        _, percussive = librosa.effects.hpss(waveform)
        onset_envelope = np.asarray(
            librosa.onset.onset_strength(
                y=np.asarray(percussive, dtype=np.float32),
                sr=sample_rate,
                hop_length=self.hop_length,
                aggregate=np.median,
            ),
            dtype=float,
        )
        tempo_raw, beat_frames_raw = librosa.beat.beat_track(
            onset_envelope=onset_envelope,
            sr=sample_rate,
            hop_length=self.hop_length,
        )
        tempo = self._first_scalar(tempo_raw, np)
        beat_frames = np.asarray(beat_frames_raw, dtype=int).reshape(-1)
        if tempo is None or not 20.0 <= tempo <= 400.0 or beat_frames.size < 2:
            return self._unavailable(
                track_id=track_id,
                duration=duration,
                provenance=provenance,
                reason="INSUFFICIENT_BEAT_EVIDENCE",
            )

        valid_frames = beat_frames[
            (beat_frames >= 0) & (beat_frames < max(len(onset_envelope), 1))
        ]
        if valid_frames.size < 2:
            return self._unavailable(
                track_id=track_id,
                duration=duration,
                provenance=provenance,
                reason="INSUFFICIENT_VALID_BEAT_FRAMES",
            )

        beat_times = np.asarray(
            librosa.frames_to_time(
                valid_frames,
                sr=sample_rate,
                hop_length=self.hop_length,
            ),
            dtype=float,
        )
        finite_mask = np.isfinite(beat_times) & (beat_times >= 0.0) & (beat_times <= duration)
        valid_frames = valid_frames[finite_mask]
        beat_times = beat_times[finite_mask]
        if beat_times.size < 2 or np.any(np.diff(beat_times) <= 0.0):
            return self._unavailable(
                track_id=track_id,
                duration=duration,
                provenance=provenance,
                reason="INVALID_BEAT_TIMESTAMPS",
            )

        tempo_confidence, stability, reference_strength = self._tempo_confidence(
            tempo=float(tempo),
            beat_frames=valid_frames,
            beat_times=beat_times,
            onset_envelope=onset_envelope,
            duration=duration,
            np=np,
        )
        events = tuple(
            BeatEvent(
                index=index,
                time_seconds=float(time_seconds),
                confidence=self._beat_confidence(
                    frame=int(frame),
                    onset_envelope=onset_envelope,
                    reference_strength=reference_strength,
                    stability=stability,
                ),
                is_downbeat=None,
                downbeat_confidence=None,
            )
            for index, (frame, time_seconds) in enumerate(
                zip(valid_frames, beat_times, strict=True)
            )
        )
        warnings = (
            "shadow-only beat-grid candidate; no runtime authority",
            "beat and tempo confidence are derived heuristics and are not benchmark-calibrated",
            "downbeat and meter evidence unavailable; WB006D remains on hold",
        )
        return RhythmicStructureAnalysis(
            track_id=track_id,
            duration_seconds=duration,
            beat_grid=BeatGrid(
                status=EvidenceStatus.DERIVED,
                beats=events,
                provenance=provenance,
                tempo_bpm=float(tempo),
                tempo_confidence=tempo_confidence,
                meter_beats_per_bar=None,
                meter_confidence=None,
                warnings=warnings,
            ),
            warnings=warnings,
        )

    @staticmethod
    def _validated_source(path: str) -> Path:
        if not isinstance(path, str) or not path.strip():
            raise ValueError("analysis path must be a non-empty string")
        source = Path(path)
        if not source.is_absolute():
            raise ValueError("analysis path must be absolute")
        try:
            resolved = source.resolve(strict=True)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"audio file not found: {source}") from exc
        if not resolved.is_file():
            raise ValueError("analysis path must reference a regular file")
        return resolved

    @staticmethod
    def _validate_duration_binding(observed: float, canonical: float | None) -> None:
        if canonical is None:
            return
        tolerance = max(0.05, canonical * 0.001)
        if abs(observed - canonical) > tolerance:
            raise ValueError("shadow audio duration does not match canonical evidence")

    @staticmethod
    def _first_scalar(value: Any, np: Any) -> float | None:
        values = np.asarray(value, dtype=float).reshape(-1)
        if values.size == 0:
            return None
        scalar = float(values[0])
        return scalar if math.isfinite(scalar) else None

    @staticmethod
    def _clip(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _tempo_confidence(
        self,
        *,
        tempo: float,
        beat_frames: Any,
        beat_times: Any,
        onset_envelope: Any,
        duration: float,
        np: Any,
    ) -> tuple[float, float, float]:
        intervals = np.diff(np.asarray(beat_times, dtype=float))
        intervals = intervals[np.isfinite(intervals) & (intervals > 0.0)]
        if intervals.size == 0:
            return 0.0, 0.0, 0.0

        median_interval = float(np.median(intervals))
        deviation = float(np.median(np.abs(intervals - median_interval)))
        stability = self._clip(1.0 - ((deviation / max(median_interval, 1e-12)) * 8.0))
        expected_beats = max(1.0, duration * tempo / 60.0)
        coverage = self._clip(len(beat_frames) / expected_beats)

        positive = onset_envelope[np.isfinite(onset_envelope) & (onset_envelope > 0.0)]
        reference_strength = float(np.percentile(positive, 95)) if positive.size else 0.0
        if reference_strength > 0.0:
            local = onset_envelope[beat_frames]
            strength = self._clip(float(np.mean(local)) / reference_strength)
        else:
            strength = 0.0
        confidence = self._clip((0.50 * stability) + (0.30 * coverage) + (0.20 * strength))
        return confidence, stability, reference_strength

    def _beat_confidence(
        self,
        *,
        frame: int,
        onset_envelope: Any,
        reference_strength: float,
        stability: float,
    ) -> float:
        if reference_strength <= 0.0 or frame < 0 or frame >= len(onset_envelope):
            local_strength = 0.0
        else:
            local_strength = self._clip(float(onset_envelope[frame]) / reference_strength)
        return self._clip((0.70 * local_strength) + (0.30 * stability))

    @staticmethod
    def _unavailable(
        *,
        track_id: str,
        duration: float,
        provenance: EvidenceProvenance,
        reason: str,
    ) -> RhythmicStructureAnalysis:
        warnings = (
            "shadow-only beat-grid candidate produced no usable beat evidence",
            "WB006D remains on hold; no downbeat, meter, phrase, or structure inference ran",
        )
        return RhythmicStructureAnalysis(
            track_id=track_id,
            duration_seconds=duration,
            beat_grid=BeatGrid(
                status=EvidenceStatus.UNAVAILABLE,
                beats=(),
                provenance=provenance,
                warnings=warnings,
                unavailable_reason=reason,
            ),
            warnings=warnings,
        )


__all__ = ["LibrosaBeatGridShadowAnalyzer"]
