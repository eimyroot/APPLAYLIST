from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from core.analysis.inspector_contract import (
    AnalysisInspectorFilter,
    AnalysisInspectorItem,
)
from data.models.analysis_evidence_record import AnalysisEvidenceRecord
from data.repositories.analysis_evidence_repository import AnalysisEvidenceRepository
from data.repositories.track_repository import TrackRepository
from services.analysis.result_store import AnalysisResultStore


class AnalysisInspectorService:
    def __init__(
        self,
        *,
        evidence_repository: AnalysisEvidenceRepository | None = None,
        track_repository: TrackRepository | None = None,
    ) -> None:
        self._evidence = evidence_repository or AnalysisEvidenceRepository()
        self._tracks = track_repository or TrackRepository()

    def list_items(
        self,
        filter_by: AnalysisInspectorFilter = "all",
    ) -> list[AnalysisInspectorItem]:
        if filter_by not in {"all", "uncertain", "failed", "corrected"}:
            raise ValueError("unknown analysis inspector filter")
        items = [self._build_item(attempt) for attempt in self._evidence.list_latest_attempts()]
        if filter_by == "uncertain":
            return [item for item in items if item.uncertain]
        if filter_by == "failed":
            return [item for item in items if item.status == "failed"]
        if filter_by == "corrected":
            return [item for item in items if item.corrected]
        return items

    def get_item(self, track_id: str) -> AnalysisInspectorItem | None:
        attempt = self._evidence.latest_evidence_for_track(track_id)
        if attempt is None:
            return None
        return self._build_item(attempt)

    def apply_correction(
        self,
        *,
        track_id: str,
        values: Mapping[str, object],
        reason: str | None = None,
    ) -> AnalysisInspectorItem:
        latest_success = self._evidence.latest_success_for_track(track_id)
        if latest_success is None:
            raise ValueError("manual correction requires successful provider evidence")
        self._evidence.append_correction(
            track_id=track_id,
            base_evidence_id=latest_success.evidence_id,
            values=values,
            reason=reason,
        )
        item = self.get_item(track_id)
        if item is None:
            raise RuntimeError("corrected track disappeared from inspector")
        return item

    def _build_item(self, attempt: AnalysisEvidenceRecord) -> AnalysisInspectorItem:
        success = self._evidence.latest_success_for_track(attempt.track_id)
        correction = (
            self._evidence.latest_active_correction(attempt.track_id, success.evidence_id)
            if success is not None
            else None
        )
        correction_values = (
            self._decode_correction(correction.payload_json)
            if correction is not None
            else {}
        )
        base = success
        track = self._tracks.get_by_id(attempt.track_id)
        title = attempt.track_id
        artist: str | None = None
        if track is not None:
            if isinstance(track.title, str) and track.title.strip():
                title = track.title.strip()
            elif isinstance(track.path, str) and track.path.strip():
                title = Path(track.path).name or attempt.track_id
            if isinstance(track.artist, str) and track.artist.strip():
                artist = track.artist.strip()

        provider_source = base or attempt
        bpm = self._corrected_value(correction_values, "bpm", base.bpm if base else None)
        key_tonic = self._corrected_value(
            correction_values,
            "key_tonic",
            base.key_tonic if base else None,
        )
        key_scale = self._corrected_value(
            correction_values,
            "key_scale",
            base.key_scale if base else None,
        )
        camelot = self._corrected_value(
            correction_values,
            "camelot",
            base.camelot if base else None,
        )
        energy = self._corrected_value(
            correction_values,
            "energy",
            base.energy if base else None,
        )

        return AnalysisInspectorItem(
            track_id=attempt.track_id,
            title=title,
            artist=artist,
            status=attempt.status,  # type: ignore[arg-type]
            bpm=bpm if isinstance(bpm, (int, float)) else None,
            bpm_confidence=base.bpm_confidence if base else None,
            key_tonic=key_tonic if isinstance(key_tonic, str) else None,
            key_scale=key_scale if isinstance(key_scale, str) else None,
            camelot=camelot if isinstance(camelot, str) else None,
            key_confidence=base.key_confidence if base else None,
            energy=energy if isinstance(energy, (int, float)) else None,
            duration_seconds=base.duration_seconds if base else None,
            provider=provider_source.provider,
            provider_version=provider_source.provider_version,
            analysis_version=provider_source.analysis_version,
            algorithm_version=provider_source.algorithm_version,
            warnings=base.warnings if base else attempt.warnings,
            source="manual-correction" if correction is not None else "provider",
            uncertain=AnalysisResultStore.is_uncertain_evidence(base),
            corrected=correction is not None,
            attempt_evidence_id=attempt.evidence_id,
            effective_evidence_id=base.evidence_id if base else None,
            correction_id=correction.correction_id if correction else None,
            correction_reason=correction.reason if correction else None,
            error_code=attempt.error_code if attempt.status == "failed" else None,
            error_detail=attempt.error_detail if attempt.status == "failed" else None,
        )

    @staticmethod
    def _decode_correction(payload_json: str) -> dict[str, object]:
        value = json.loads(payload_json)
        if not isinstance(value, dict):
            raise ValueError("stored correction payload is invalid")
        allowed = {"bpm", "key_tonic", "key_scale", "camelot", "energy"}
        if set(value) - allowed:
            raise ValueError("stored correction payload contains unsupported fields")
        return value

    @staticmethod
    def _corrected_value(
        correction: Mapping[str, object],
        field: str,
        provider_value: object,
    ) -> object:
        return correction[field] if field in correction else provider_value
