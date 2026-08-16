from __future__ import annotations

from core.analysis.provider_contract import (
    CanonicalAnalysisResult,
    ProviderContractError,
    ProviderOutputInvalid,
    ProviderRuntimeFailure,
    ProviderUnavailableError,
    UnknownProviderError,
)
from data.models.analysis_evidence_record import AnalysisEvidenceRecord
from data.repositories.analysis_evidence_repository import AnalysisEvidenceRepository

INSPECTOR_CONFIDENCE_FLOOR = 0.50


class AnalysisResultStore:
    def __init__(self, repository: AnalysisEvidenceRepository | None = None) -> None:
        self._repo = repository or AnalysisEvidenceRepository()

    def persist_success(
        self,
        *,
        track_id: str,
        result: CanonicalAnalysisResult,
    ) -> AnalysisEvidenceRecord:
        return self._repo.append_evidence(
            track_id=track_id,
            provider=result.provider,
            analysis_version=result.analysis_version,
            status="succeeded",
            provider_version=result.provider_version,
            algorithm_version=result.algorithm_version,
            bpm=result.bpm,
            bpm_confidence=result.bpm_confidence,
            key_tonic=result.key_tonic,
            key_scale=result.key_scale,
            camelot=result.camelot,
            key_confidence=result.key_confidence,
            energy=result.energy,
            loudness_db=result.loudness_db,
            duration_seconds=result.duration_seconds,
            beat_stability=result.beat_stability,
            harmonic_ratio=result.harmonic_ratio,
            percussive_ratio=result.percussive_ratio,
            genre_hint=result.genre_hint,
            warnings=result.warnings,
        )

    def persist_failure(
        self,
        *,
        track_id: str,
        preferred_provider: str | None,
        error: Exception,
    ) -> AnalysisEvidenceRecord:
        provider, code, detail = self.safe_failure(error, preferred_provider=preferred_provider)
        return self._repo.append_evidence(
            track_id=track_id,
            provider=provider,
            analysis_version="canonical-mir-v1",
            status="failed",
            error_code=code,
            error_detail=detail,
        )

    @staticmethod
    def is_uncertain(result: CanonicalAnalysisResult) -> bool:
        return (
            result.bpm is None
            or result.camelot is None
            or result.energy is None
            or result.bpm_confidence is None
            or result.bpm_confidence < INSPECTOR_CONFIDENCE_FLOOR
            or result.key_confidence is None
            or result.key_confidence < INSPECTOR_CONFIDENCE_FLOOR
        )

    @staticmethod
    def is_uncertain_evidence(evidence: AnalysisEvidenceRecord | None) -> bool:
        if evidence is None or evidence.status != "succeeded":
            return False
        return (
            evidence.bpm is None
            or evidence.camelot is None
            or evidence.energy is None
            or evidence.bpm_confidence is None
            or evidence.bpm_confidence < INSPECTOR_CONFIDENCE_FLOOR
            or evidence.key_confidence is None
            or evidence.key_confidence < INSPECTOR_CONFIDENCE_FLOOR
        )

    @staticmethod
    def safe_failure(
        error: Exception,
        *,
        preferred_provider: str | None,
    ) -> tuple[str, str, str]:
        provider = preferred_provider.strip().lower() if preferred_provider else "unresolved"
        if isinstance(error, ProviderContractError) and error.provider:
            provider = error.provider.strip().lower() or provider

        if isinstance(error, UnknownProviderError):
            return provider, error.code, "Requested analysis provider is unknown."
        if isinstance(error, ProviderOutputInvalid):
            return provider, error.code, "Analysis provider returned invalid output."
        if isinstance(error, ProviderRuntimeFailure):
            return provider, error.code, "Analysis provider failed for this track."
        if isinstance(error, ProviderUnavailableError):
            return provider, error.code, "Analysis provider is unavailable."
        if isinstance(error, ProviderContractError):
            return provider, error.code, "Analysis failed with a controlled provider error."
        if isinstance(error, LookupError):
            return provider, "track_unavailable", "Track is not available for analysis."
        return provider, "analysis_internal_error", "Analysis failed for this track."
