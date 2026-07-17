from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol
from uuid import uuid4

from services.composer.composer import Composer
from services.composition.export_service import CanonicalCompositionExportService
from services.composition.runner import CanonicalCompositionExecutionRequest
from services.export.exporter import Exporter


@dataclass(frozen=True, slots=True)
class PipelineCompositionCommand:
    path: str
    limit: int
    bpm_min: float | None = None
    bpm_max: float | None = None
    mode: str | None = None


@dataclass(frozen=True, slots=True)
class PipelineCompositionOutcome:
    run_id: str
    tracks: tuple[object, ...]
    export: Mapping[str, object]


class PipelineCompositionAuthority(Protocol):
    authority_name: str

    def execute(
        self,
        command: PipelineCompositionCommand,
    ) -> PipelineCompositionOutcome: ...


class LegacyComposer(Protocol):
    def compose(self, limit: int) -> list: ...


class PlaylistExporter(Protocol):
    def export_m3u(self, *, playlist_id: str, tracks: list) -> dict: ...


class CanonicalExportExecutor(Protocol):
    def execute(self, request: CanonicalCompositionExecutionRequest): ...


def new_pipeline_run_id() -> str:
    return f"pipeline-{uuid4().hex}"


class LegacyCompositionAuthority:
    """Preserve the existing composer, run-ID and exporter behavior."""

    authority_name = "legacy"

    def __init__(
        self,
        *,
        composer: LegacyComposer | None = None,
        exporter: PlaylistExporter | None = None,
        run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.composer = composer if composer is not None else Composer()
        self.exporter = exporter if exporter is not None else Exporter()
        self._run_id_factory = run_id_factory or new_pipeline_run_id

    def execute(
        self,
        command: PipelineCompositionCommand,
    ) -> PipelineCompositionOutcome:
        playlist = list(self.composer.compose(limit=command.limit))
        run_id = self._run_id_factory()
        if not isinstance(run_id, str) or not run_id.strip():
            raise RuntimeError("Pipeline run ID factory returned an invalid identifier")
        normalized_run_id = run_id.strip()
        export = self.exporter.export_m3u(
            playlist_id=normalized_run_id,
            tracks=playlist,
        )
        return PipelineCompositionOutcome(
            run_id=normalized_run_id,
            tracks=tuple(playlist),
            export=MappingProxyType(dict(export)),
        )


class CanonicalCompositionAuthority:
    """Explicit canonical authority backed by the isolated export service."""

    authority_name = "canonical"

    def __init__(
        self,
        *,
        service: CanonicalExportExecutor | None = None,
    ) -> None:
        self._service = (
            service if service is not None else CanonicalCompositionExportService()
        )

    def execute(
        self,
        command: PipelineCompositionCommand,
    ) -> PipelineCompositionOutcome:
        result = self._service.execute(
            CanonicalCompositionExecutionRequest(
                target_track_count=command.limit,
                bpm_min=command.bpm_min if command.bpm_min is not None else 1.0,
                bpm_max=command.bpm_max if command.bpm_max is not None else 300.0,
                mode=command.mode if command.mode is not None else "club",
            )
        )
        if not result.exported or result.run_id is None or result.artifact is None:
            raise RuntimeError("Canonical composition did not produce an exportable playlist")

        artifact = result.artifact
        export = {
            "playlist_id": artifact.playlist_id,
            "m3u_path": artifact.m3u_path,
            "manifest_path": artifact.manifest_path,
            "warnings_path": artifact.warnings_path,
            "audit_path": artifact.audit_path,
            "resolved_count": artifact.resolved_count,
            "skipped_count": artifact.skipped_count,
        }
        return PipelineCompositionOutcome(
            run_id=result.run_id,
            tracks=tuple(result.execution.tracks),
            export=MappingProxyType(export),
        )
