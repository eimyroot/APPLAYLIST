from __future__ import annotations

import math
from pathlib import Path
from typing import Any


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

CAMELOT_BY_PITCH_CLASS = {
    "major": (
        "8B", "3B", "10B", "5B", "12B", "7B", "2B", "9B", "4B", "11B", "6B", "1B"
    ),
    "minor": (
        "5A", "12A", "7A", "2A", "9A", "4A", "11A", "6A", "1A", "8A", "3A", "10A"
    ),
}

MAJOR_PROFILE = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
MINOR_PROFILE = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)


class BaselineLibrosaMIR:
    """Deterministic local baseline for benchmark evaluation, not production approval."""

    provider_name = "librosa"
    algorithm_version = "baseline-librosa-mir-v1"
    sample_rate = 22_050
    hop_length = 512

    def analyze(self, path: str) -> dict[str, Any]:
        source = self._validated_source(path)

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
        if float(np.max(np.abs(waveform))) < 1e-7:
            raise ValueError("decoded audio is silent")

        warnings = [
            "baseline provider output is not benchmark-approved",
            "confidence values are internal and not benchmark-calibrated",
            "energy score is relative and provider-specific",
        ]
        if duration < 3.0:
            warnings.append("short audio may reduce tempo and key reliability")

        harmonic, percussive = librosa.effects.hpss(waveform)
        harmonic = np.asarray(harmonic, dtype=np.float32)
        percussive = np.asarray(percussive, dtype=np.float32)

        onset_envelope = librosa.onset.onset_strength(
            y=percussive,
            sr=sample_rate,
            hop_length=self.hop_length,
            aggregate=np.median,
        )
        tempo_raw, beat_frames = librosa.beat.beat_track(
            onset_envelope=onset_envelope,
            sr=sample_rate,
            hop_length=self.hop_length,
        )
        tempo = self._first_scalar(tempo_raw, np)
        beat_frames = np.asarray(beat_frames, dtype=int)
        bpm, bpm_confidence, beat_stability = self._beat_evidence(
            tempo=tempo,
            beat_frames=beat_frames,
            onset_envelope=np.asarray(onset_envelope, dtype=float),
            duration=duration,
            sample_rate=sample_rate,
            librosa=librosa,
            np=np,
        )
        if bpm is None:
            warnings.append("tempo could not be estimated reliably")

        chroma = self._chroma(
            harmonic=harmonic,
            sample_rate=sample_rate,
            duration=duration,
            librosa=librosa,
            np=np,
            warnings=warnings,
        )
        tonic, scale, camelot, key_confidence = self._key_evidence(chroma, np=np)
        if camelot is None:
            warnings.append("tonal key could not be estimated reliably")

        rms = librosa.feature.rms(
            y=waveform,
            frame_length=2048,
            hop_length=self.hop_length,
        )[0]
        centroid = librosa.feature.spectral_centroid(
            y=waveform,
            sr=sample_rate,
            hop_length=self.hop_length,
        )[0]
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=onset_envelope,
            sr=sample_rate,
            hop_length=self.hop_length,
            units="frames",
        )

        harmonic_power = float(np.sum(np.square(harmonic, dtype=np.float64)))
        percussive_power = float(np.sum(np.square(percussive, dtype=np.float64)))
        total_power = harmonic_power + percussive_power
        if total_power <= 1e-20:
            harmonic_ratio = 0.5
            percussive_ratio = 0.5
        else:
            harmonic_ratio = self._clip(harmonic_power / total_power)
            percussive_ratio = self._clip(percussive_power / total_power)

        loudness_db, energy = self._energy_evidence(
            rms=np.asarray(rms, dtype=float),
            centroid=np.asarray(centroid, dtype=float),
            onset_count=int(len(onset_frames)),
            duration=duration,
            sample_rate=sample_rate,
            percussive_ratio=percussive_ratio,
            np=np,
        )

        return {
            "provider": self.provider_name,
            "provider_version": str(librosa.__version__),
            "algorithm_version": self.algorithm_version,
            "status": "ok",
            "beat": {
                "bpm": bpm,
                "confidence": bpm_confidence,
                "stability": beat_stability,
                "beat_count": int(len(beat_frames)),
            },
            "key": {
                "tonic": tonic,
                "scale": scale,
                "camelot": camelot,
                "confidence": key_confidence,
            },
            "metrics": {
                "energy_score": energy,
                "loudness_db": loudness_db,
                "duration_seconds": duration,
                "harmonic_ratio": harmonic_ratio,
                "percussive_ratio": percussive_ratio,
            },
            "provenance": {
                "provider_version": str(librosa.__version__),
                "algorithm_version": self.algorithm_version,
                "sample_rate": sample_rate,
                "hop_length": self.hop_length,
            },
            "warnings": warnings,
        }

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
    def _first_scalar(value: Any, np: Any) -> float | None:
        values = np.asarray(value, dtype=float).reshape(-1)
        if values.size == 0:
            return None
        scalar = float(values[0])
        return scalar if math.isfinite(scalar) else None

    def _beat_evidence(
        self,
        *,
        tempo: float | None,
        beat_frames: Any,
        onset_envelope: Any,
        duration: float,
        sample_rate: int,
        librosa: Any,
        np: Any,
    ) -> tuple[float | None, float | None, float | None]:
        if tempo is None or not 20.0 <= tempo <= 400.0 or len(beat_frames) < 2:
            return None, 0.0, 0.0

        beat_times = librosa.frames_to_time(
            beat_frames,
            sr=sample_rate,
            hop_length=self.hop_length,
        )
        intervals = np.diff(np.asarray(beat_times, dtype=float))
        intervals = intervals[np.isfinite(intervals) & (intervals > 0.0)]
        if intervals.size == 0:
            return float(tempo), 0.0, 0.0

        median_interval = float(np.median(intervals))
        median_deviation = float(np.median(np.abs(intervals - median_interval)))
        relative_deviation = median_deviation / max(median_interval, 1e-12)
        stability = self._clip(1.0 - (relative_deviation * 8.0))

        expected_beats = max(1.0, duration * float(tempo) / 60.0)
        coverage = self._clip(len(beat_frames) / expected_beats)

        valid_frames = beat_frames[(beat_frames >= 0) & (beat_frames < len(onset_envelope))]
        if len(valid_frames) and float(np.max(onset_envelope)) > 0.0:
            reference = float(np.percentile(onset_envelope, 95))
            strength = self._clip(
                float(np.mean(onset_envelope[valid_frames])) / max(reference, 1e-12)
            )
        else:
            strength = 0.0

        confidence = self._clip((0.50 * stability) + (0.30 * coverage) + (0.20 * strength))
        return float(tempo), confidence, stability

    def _chroma(
        self,
        *,
        harmonic: Any,
        sample_rate: int,
        duration: float,
        librosa: Any,
        np: Any,
        warnings: list[str],
    ) -> Any:
        if duration >= 3.0:
            try:
                chroma = librosa.feature.chroma_cqt(
                    y=harmonic,
                    sr=sample_rate,
                    hop_length=self.hop_length,
                    bins_per_octave=36,
                )
                if np.asarray(chroma).shape[0] == 12:
                    return np.asarray(chroma, dtype=float)
            except Exception:
                warnings.append("CQT chroma failed; STFT chroma fallback used")
        else:
            warnings.append("STFT chroma used for short audio")

        return np.asarray(
            librosa.feature.chroma_stft(
                y=harmonic,
                sr=sample_rate,
                hop_length=self.hop_length,
            ),
            dtype=float,
        )

    def _key_evidence(self, chroma: Any, *, np: Any) -> tuple[str | None, str | None, str | None, float]:
        matrix = np.asarray(chroma, dtype=float)
        if matrix.ndim != 2 or matrix.shape[0] != 12 or matrix.shape[1] == 0:
            return None, None, None, 0.0
        if not np.all(np.isfinite(matrix)):
            return None, None, None, 0.0

        chroma_mean = np.median(matrix, axis=1)
        if float(np.sum(np.abs(chroma_mean))) <= 1e-12:
            return None, None, None, 0.0

        def normalized(vector: Any) -> Any:
            centered = np.asarray(vector, dtype=float) - float(np.mean(vector))
            norm = float(np.linalg.norm(centered))
            return centered / max(norm, 1e-12)

        candidates: list[tuple[float, int, str]] = []
        for scale, profile in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE)):
            profile_vector = normalized(profile)
            for tonic_index in range(12):
                rotated = np.roll(chroma_mean, -tonic_index)
                score = float(np.dot(normalized(rotated), profile_vector))
                candidates.append((score, tonic_index, scale))

        candidates.sort(key=lambda item: item[0], reverse=True)
        best_score, tonic_index, scale = candidates[0]
        second_score = candidates[1][0]
        absolute = self._clip((best_score + 1.0) / 2.0)
        margin = self._clip((best_score - second_score) / 0.20)
        confidence = self._clip((0.70 * absolute) + (0.30 * margin))
        if best_score < 0.05:
            return None, None, None, confidence

        tonic = NOTE_NAMES[tonic_index]
        camelot = CAMELOT_BY_PITCH_CLASS[scale][tonic_index]
        return tonic, scale, camelot, confidence

    def _energy_evidence(
        self,
        *,
        rms: Any,
        centroid: Any,
        onset_count: int,
        duration: float,
        sample_rate: int,
        percussive_ratio: float,
        np: Any,
    ) -> tuple[float, float]:
        finite_rms = rms[np.isfinite(rms) & (rms >= 0.0)]
        if finite_rms.size == 0:
            raise ValueError("RMS analysis produced no finite values")

        rms_mean = float(np.mean(finite_rms))
        loudness_db = 20.0 * math.log10(max(rms_mean, 1e-12))
        loudness_component = self._clip((loudness_db + 35.0) / 29.0)

        finite_centroid = centroid[np.isfinite(centroid) & (centroid >= 0.0)]
        centroid_mean = float(np.mean(finite_centroid)) if finite_centroid.size else 0.0
        brightness = self._clip(centroid_mean / min(6_000.0, sample_rate / 2.0))
        onset_activity = self._clip((onset_count / max(duration, 1e-12)) / 4.0)

        p10 = float(np.percentile(finite_rms, 10))
        p90 = float(np.percentile(finite_rms, 90))
        dynamics = self._clip((p90 - p10) / max(p90, 1e-12))

        energy = self._clip(
            (0.40 * loudness_component)
            + (0.25 * percussive_ratio)
            + (0.20 * onset_activity)
            + (0.10 * brightness)
            + (0.05 * dynamics)
        )
        return loudness_db, energy

    @staticmethod
    def _clip(value: float) -> float:
        if not math.isfinite(value):
            return 0.0
        return max(0.0, min(1.0, float(value)))
