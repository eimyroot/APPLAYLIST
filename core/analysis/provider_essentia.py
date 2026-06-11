from __future__ import annotations

import os
from typing import Any, Dict, Optional


def essentia_enabled() -> bool:
    return os.getenv("APPLAYLIST_ENABLE_ESSENTIA", "0") == "1"


def _import_essentia_standard():
    import essentia.standard as es  # type: ignore
    return es


def essentia_available() -> bool:
    if not essentia_enabled():
        return False
    try:
        _import_essentia_standard()
        return True
    except Exception:
        return False


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def analyze_with_essentia(path: str) -> Dict[str, Any]:
    if not essentia_enabled():
        raise RuntimeError("Essentia provider disabled. Set APPLAYLIST_ENABLE_ESSENTIA=1")
    if not essentia_available():
        raise RuntimeError("Essentia provider not available in current environment")

    es = _import_essentia_standard()
    warnings = []

    loader = es.MonoLoader(filename=path)
    audio = loader()

    duration_seconds = None
    sample_rate_hz = None

    try:
        duration_seconds = _safe_float(len(audio) / 44100.0)
        sample_rate_hz = 44100
    except Exception:
        warnings.append("failed to derive duration/sample_rate from loaded audio")

    rhythm_bpm = None
    try:
        rhythm = es.RhythmExtractor2013(method="multifeature")
        bpm, _, _, _, _ = rhythm(audio)
        rhythm_bpm = _safe_float(bpm)
    except Exception as exc:
        warnings.append(f"rhythm extraction failed: {exc.__class__.__name__}")

    key_key = None
    key_scale = None
    key_strength = None
    try:
        key_extractor = es.KeyExtractor()
        key, scale, strength = key_extractor(audio)
        key_key = f"{key} {scale}"
        key_scale = scale
        key_strength = _safe_float(strength)
    except Exception as exc:
        warnings.append(f"key extraction failed: {exc.__class__.__name__}")

    loudness_energy = None
    loudness_integrated_lufs = None
    try:
        loudness_energy = _safe_float(es.Energy()(audio))
    except Exception as exc:
        warnings.append(f"energy extraction failed: {exc.__class__.__name__}")

    try:
        loudness_integrated_lufs = _safe_float(es.LoudnessEBUR128(sampleRate=44100)(audio)[0])
    except Exception as exc:
        warnings.append(f"lufs extraction failed: {exc.__class__.__name__}")

    return {
        "provider": "essentia",
        "source_path": path,
        "provider_version": None,
        "rhythm_bpm": rhythm_bpm,
        "key_key": key_key,
        "key_scale": key_scale,
        "key_strength": key_strength,
        "loudness_energy": loudness_energy,
        "loudness_integrated_lufs": loudness_integrated_lufs,
        "duration_seconds": duration_seconds,
        "sample_rate_hz": sample_rate_hz,
        "warnings": warnings,
    }
