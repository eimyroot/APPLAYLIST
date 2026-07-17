from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from services.composition.models import CompositionStatus, CompositionTrack
from services.composition.runner import (
    CanonicalCompositionExecutionRequest,
    CanonicalCompositionExecutionResult,
    CanonicalCompositionRunner,
)
from services.export.exporter import Exporter


_SAFE_RUN_ID = re.compile(r"^canonical-[A-Za-z0-9_-]{1,96}$")


class CanonicalCompositionExecutor(Protocol):
    def run(
        self,
        request: CanonicalCompositionExecutionRequest,
    ) -> CanonicalCompositionExecutionResult: ...


class PlaylistExporter(Protocol):
    def export_m3u(
        self,
        *,
        playlist_id: str,
        tracks: list[CompositionTrack],
    ) -> dict: ...


@dataclass(frozen=True, slots=True)
class CanonicalCompositionExportArtifact:
    playlist_id: str
    m3u_path: str
    manifest_path: str
    warnings_path: str
    audit_path: str
    resolved_count: int
    skipped_count: int


@dataclass(frozen=True, slots=True)
class CanonicalCompositionExportResult:
    execution: CanonicalCompositionExecutionResult
    run_id: str | None
    artifact: CanonicalCompositionExportArtifact | None

    @property
    def exported(self) -> bool:
        return self.artifact is not None


class CanonicalCompositionExportService:
    """Explicit canonical export boundary; never invoked by the legacy pipeline."""

    def __init__(
        self,
        *,
        runner: CanonicalCompositionExecutor | None = None,
        exporter: PlaylistExporter | None = None,
        run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._runner = runner if runner is not None else CanonicalCompositionRunner()
        self._exporter = exporter if exporter is not None else Exporter()
        self._run_id_factory = run_id_factory or _new_canonical_run_id

    def execute(
        self,
        request: CanonicalCompositionExecutionRequest,
    ) -> CanonicalCompositionExportResult:
        execution = self._runner.run(request)
        if (
            execution.composition.status == CompositionStatus.FAILED
            or not execution.tracks
        ):
            return CanonicalCompositionExportResult(
                execution=execution,
                run_id=None,
                artifact=None,
            )

        run_id = _validate_run_id(self._run_id_factory())
        raw_artifact = self._exporter.export_m3u(
            playlist_id=run_id,
            tracks=list(execution.tracks),
        )
        artifact = _materialize_artifact(
            raw_artifact,
            expected_run_id=run_id,
            expected_track_count=len(execution.tracks),
        )
        return CanonicalCompositionExportResult(
            execution=execution,
            run_id=run_id,
            artifact=artifact,
        )


def _new_canonical_run_id() -> str:
    return f"canonical-{uuid4().hex}"


def _validate_run_id(value: object) -> str:
    if not isinstance(value, str):
        raise RuntimeError("Canonical run ID factory returned a non-string identifier")
    normalized = value.strip()
    if not _SAFE_RUN_ID.fullmatch(normalized):
        raise RuntimeError("Canonical run ID factory returned an unsafe identifier")
    return normalized


def _materialize_artifact(
    payload: Mapping[str, object],
    *,
    expected_run_id: str,
    expected_track_count: int,
) -> CanonicalCompositionExportArtifact:
    playlist_id = _required_text(payload, "playlist_id")
    if playlist_id != expected_run_id:
        raise RuntimeError("Exporter returned a mismatched playlist identifier")

    resolved_count = _required_count(payload, "resolved_count")
    skipped_count = _required_count(payload, "skipped_count")
    if resolved_count != expected_track_count:
        raise RuntimeError("Exporter did not resolve every canonical track")
    if skipped_count != 0:
        raise RuntimeError("Exporter skipped one or more canonical tracks")

    return CanonicalCompositionExportArtifact(
        playlist_id=playlist_id,
        m3u_path=_required_text(payload, "m3u_path"),
        manifest_path=_required_text(payload, "manifest_path"),
        warnings_path=_required_text(payload, "warnings_path"),
        audit_path=_required_text(payload, "audit_path"),
        resolved_count=resolved_count,
        skipped_count=skipped_count,
    )


def _required_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Exporter returned an invalid {key}")
    return value.strip()


def _required_count(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"Exporter returned an invalid {key}")
    return value
