from __future__ import annotations

import re
import threading
from collections.abc import Mapping, Sequence
from typing import Any

from core.analysis.job_contract import AnalysisJobSnapshot, TERMINAL_ANALYSIS_JOB_STATES
from services.analysis.batch_runner import AnalysisBatchRunner
from services.analysis.inspector import AnalysisInspectorService
from services.analysis.job_service import AnalysisJobService

MAX_DESKTOP_ANALYSIS_TRACKS = 10_000
MAX_TRACK_ID_CHARS = 256
MAX_PROVIDER_CHARS = 128
MAX_CORRECTION_REASON_CHARS = 512

_ANALYSIS_JOB_ID = re.compile(r"^aj_[0-9a-f]{32}$")
_ALLOWED_FILTERS = frozenset({"all", "uncertain", "failed", "corrected"})
_ALLOWED_CORRECTION_FIELDS = frozenset({"bpm", "key_tonic", "key_scale", "camelot", "energy"})


class DesktopAnalysisTransportError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DesktopAnalysisTransport:
    """Trusted sidecar adapter around the persisted Bundle 50 analysis services.

    The transport accepts stable track identifiers only. It never accepts or returns
    filesystem paths, process identifiers, sidecar credentials, or raw exceptions.
    """

    def __init__(
        self,
        *,
        jobs: AnalysisJobService | None = None,
        inspector: AnalysisInspectorService | None = None,
    ) -> None:
        self._jobs = jobs or AnalysisJobService()
        self._inspector = inspector or AnalysisInspectorService()
        self._lock = threading.Lock()
        self._active_job_id: str | None = None

    def start(
        self,
        *,
        track_ids: Sequence[str],
        preferred_provider: str | None = None,
    ) -> dict[str, object]:
        normalized_tracks = self._validated_track_ids(track_ids)
        provider = self._validated_provider(preferred_provider)
        with self._lock:
            if self._has_active_job_locked():
                raise DesktopAnalysisTransportError(
                    "analysis_busy",
                    "An analysis job is already active.",
                )
            snapshot = self._jobs.create_job(
                track_ids=normalized_tracks,
                preferred_provider=provider,
            )
            self._active_job_id = snapshot.job_id
            try:
                threading.Thread(
                    target=self._run_job,
                    args=(snapshot.job_id,),
                    name="applaylist-analysis-job",
                    daemon=True,
                ).start()
            except Exception as exc:
                self._active_job_id = None
                try:
                    snapshot = self._jobs.fail_job(
                        snapshot.job_id,
                        error_code="analysis_job_start_failed",
                        error_detail="The analysis job could not start safely.",
                    )
                except Exception:
                    pass
                raise DesktopAnalysisTransportError(
                    "analysis_job_start_failed",
                    "The analysis job could not start safely.",
                ) from exc
        return self._snapshot_payload(snapshot)

    def status(self, job_id: str) -> dict[str, object]:
        normalized = self._validated_job_id(job_id)
        snapshot = self._jobs.get_job(normalized)
        if snapshot is None:
            raise DesktopAnalysisTransportError(
                "unknown_analysis_job",
                "The analysis job is not available.",
            )
        return self._snapshot_payload(snapshot)

    def cancel(self, job_id: str) -> dict[str, object]:
        normalized = self._validated_job_id(job_id)
        try:
            snapshot = self._jobs.request_cancel(normalized)
        except KeyError as exc:
            raise DesktopAnalysisTransportError(
                "unknown_analysis_job",
                "The analysis job is not available.",
            ) from exc
        return self._snapshot_payload(snapshot)

    def list_inspector(self, filter_by: str = "all") -> dict[str, object]:
        normalized_filter = self._validated_filter(filter_by)
        items = self._inspector.list_items(normalized_filter)  # type: ignore[arg-type]
        return {
            "filter": normalized_filter,
            "items": [item.to_dict() for item in items],
        }

    def get_inspector_item(self, track_id: str) -> dict[str, object]:
        normalized_track = self._validated_track_id(track_id)
        item = self._inspector.get_item(normalized_track)
        if item is None:
            raise DesktopAnalysisTransportError(
                "analysis_item_not_found",
                "No analysis evidence is available for this track.",
            )
        return item.to_dict()

    def correct(
        self,
        *,
        track_id: str,
        values: Mapping[str, object],
        reason: str | None = None,
    ) -> dict[str, object]:
        normalized_track = self._validated_track_id(track_id)
        normalized_values = self._validated_correction(values)
        normalized_reason = self._validated_reason(reason)
        try:
            item = self._inspector.apply_correction(
                track_id=normalized_track,
                values=normalized_values,
                reason=normalized_reason,
            )
        except ValueError as exc:
            raise DesktopAnalysisTransportError(
                "invalid_analysis_correction",
                "The analysis correction was rejected.",
            ) from exc
        return item.to_dict()

    def reanalyze(
        self,
        *,
        track_id: str,
        preferred_provider: str | None = None,
    ) -> dict[str, object]:
        return self.start(
            track_ids=[self._validated_track_id(track_id)],
            preferred_provider=preferred_provider,
        )

    def active_job_id(self) -> str | None:
        with self._lock:
            if not self._has_active_job_locked():
                return None
            return self._active_job_id

    def request_active_cancel(self) -> None:
        with self._lock:
            job_id = self._active_job_id
        if job_id is None:
            return
        try:
            self._jobs.request_cancel(job_id)
        except (KeyError, ValueError):
            return

    def _run_job(self, job_id: str) -> None:
        try:
            AnalysisBatchRunner(job_service=self._jobs).run(job_id)
        finally:
            with self._lock:
                if self._active_job_id == job_id:
                    self._active_job_id = None

    def _has_active_job_locked(self) -> bool:
        job_id = self._active_job_id
        if job_id is None:
            return False
        snapshot = self._jobs.get_job(job_id)
        if snapshot is None or snapshot.status in TERMINAL_ANALYSIS_JOB_STATES:
            self._active_job_id = None
            return False
        return True

    @staticmethod
    def _snapshot_payload(snapshot: AnalysisJobSnapshot) -> dict[str, object]:
        payload = snapshot.to_dict()
        payload["terminal"] = snapshot.status in TERMINAL_ANALYSIS_JOB_STATES
        return payload

    @classmethod
    def _validated_track_ids(cls, values: Sequence[str]) -> tuple[str, ...]:
        if isinstance(values, (str, bytes)):
            raise DesktopAnalysisTransportError(
                "invalid_analysis_request",
                "Analysis track_ids must be a bounded list.",
            )
        if not 1 <= len(values) <= MAX_DESKTOP_ANALYSIS_TRACKS:
            raise DesktopAnalysisTransportError(
                "invalid_analysis_request",
                "Analysis track_ids must contain between 1 and 10000 tracks.",
            )
        normalized = tuple(cls._validated_track_id(value) for value in values)
        if len(set(normalized)) != len(normalized):
            raise DesktopAnalysisTransportError(
                "invalid_analysis_request",
                "Analysis track_ids must be unique.",
            )
        return normalized

    @staticmethod
    def _validated_track_id(value: object) -> str:
        if not isinstance(value, str):
            raise DesktopAnalysisTransportError(
                "invalid_track_id",
                "The track identifier is invalid.",
            )
        normalized = value.strip()
        if (
            not normalized
            or len(normalized) > MAX_TRACK_ID_CHARS
            or normalized != value
            or any(ord(character) < 32 for character in normalized)
            or "/" in normalized
            or "\\" in normalized
        ):
            raise DesktopAnalysisTransportError(
                "invalid_track_id",
                "The track identifier is invalid.",
            )
        return normalized

    @staticmethod
    def _validated_job_id(value: object) -> str:
        if not isinstance(value, str) or _ANALYSIS_JOB_ID.fullmatch(value) is None:
            raise DesktopAnalysisTransportError(
                "invalid_analysis_job",
                "The analysis job identifier is invalid.",
            )
        return value

    @staticmethod
    def _validated_provider(value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise DesktopAnalysisTransportError(
                "invalid_analysis_provider",
                "The preferred analysis provider is invalid.",
            )
        normalized = value.strip().lower()
        if (
            not normalized
            or normalized != value.strip()
            or len(normalized) > MAX_PROVIDER_CHARS
            or any(ord(character) < 33 or ord(character) > 126 for character in normalized)
        ):
            raise DesktopAnalysisTransportError(
                "invalid_analysis_provider",
                "The preferred analysis provider is invalid.",
            )
        return normalized

    @staticmethod
    def _validated_filter(value: object) -> str:
        if not isinstance(value, str) or value not in _ALLOWED_FILTERS:
            raise DesktopAnalysisTransportError(
                "invalid_analysis_filter",
                "The analysis inspector filter is invalid.",
            )
        return value

    @staticmethod
    def _validated_reason(value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise DesktopAnalysisTransportError(
                "invalid_analysis_correction",
                "The analysis correction reason is invalid.",
            )
        normalized = value.strip()
        if not normalized or len(normalized) > MAX_CORRECTION_REASON_CHARS:
            raise DesktopAnalysisTransportError(
                "invalid_analysis_correction",
                "The analysis correction reason is invalid.",
            )
        return normalized

    @staticmethod
    def _validated_correction(values: Mapping[str, object]) -> dict[str, object]:
        if not isinstance(values, Mapping):
            raise DesktopAnalysisTransportError(
                "invalid_analysis_correction",
                "The analysis correction payload is invalid.",
            )
        normalized = dict(values)
        if not normalized or set(normalized) - _ALLOWED_CORRECTION_FIELDS:
            raise DesktopAnalysisTransportError(
                "invalid_analysis_correction",
                "The analysis correction payload is invalid.",
            )
        if "bpm" in normalized:
            bpm = normalized["bpm"]
            if isinstance(bpm, bool) or not isinstance(bpm, (int, float)) or not 20 <= float(bpm) <= 300:
                raise DesktopAnalysisTransportError(
                    "invalid_analysis_correction",
                    "The corrected BPM is invalid.",
                )
            normalized["bpm"] = float(bpm)
        if "energy" in normalized:
            energy = normalized["energy"]
            if isinstance(energy, bool) or not isinstance(energy, (int, float)) or not 0 <= float(energy) <= 1:
                raise DesktopAnalysisTransportError(
                    "invalid_analysis_correction",
                    "The corrected energy is invalid.",
                )
            normalized["energy"] = float(energy)
        for field in ("key_tonic", "key_scale", "camelot"):
            if field not in normalized:
                continue
            value = normalized[field]
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > 32:
                raise DesktopAnalysisTransportError(
                    "invalid_analysis_correction",
                    "The corrected key value is invalid.",
                )
            normalized[field] = value.strip()
        return normalized
