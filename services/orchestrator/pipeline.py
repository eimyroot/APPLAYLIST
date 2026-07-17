from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol
from uuid import uuid4

from core.config.settings import get_settings
from services.composer.composer import Composer
from services.composition.hook import (
    LoggingCompositionReceiptSink,
    PipelineCompositionComparisonHook,
)
from services.composition.receipt_sink import (
    CompositeCompositionReceiptSink,
    JsonCompositionReceiptSink,
)
from services.export.exporter import Exporter


logger = logging.getLogger(__name__)


class PipelineComparisonObserver(Protocol):
    def observe(
        self,
        *,
        run_id: str,
        legacy_track_ids: tuple[str, ...],
        target_track_count: int,
        bpm_min: float | None,
        bpm_max: float | None,
        mode: str | None,
    ) -> object: ...


def _new_pipeline_run_id() -> str:
    return f"pipeline-{uuid4().hex}"


class OrchestratorPipeline:
    def __init__(
        self,
        *,
        composer: Composer | None = None,
        exporter: Exporter | None = None,
        run_id_factory: Callable[[], str] | None = None,
        comparison_hook: PipelineComparisonObserver | None = None,
        comparison_enabled: bool | None = None,
    ) -> None:
        self.composer = composer if composer is not None else Composer()
        self.exporter = exporter if exporter is not None else Exporter()
        self._run_id_factory = run_id_factory or _new_pipeline_run_id

        settings = None
        if comparison_enabled is None or (
            comparison_enabled and comparison_hook is None
        ):
            settings = get_settings()
        if comparison_enabled is None:
            assert settings is not None
            comparison_enabled = settings.enable_composition_comparison

        self._comparison_enabled = comparison_enabled
        self._comparison_hook = comparison_hook
        if self._comparison_enabled and self._comparison_hook is None:
            assert settings is not None
            receipt_sinks: list[object] = [LoggingCompositionReceiptSink()]
            if settings.enable_composition_receipts:
                receipt_sinks.append(
                    JsonCompositionReceiptSink(settings.composition_receipts_dir)
                )
            sink = (
                receipt_sinks[0]
                if len(receipt_sinks) == 1
                else CompositeCompositionReceiptSink(tuple(receipt_sinks))
            )
            self._comparison_hook = PipelineCompositionComparisonHook(sink=sink)

    def run(
        self,
        path: str,
        limit: int = 10,
        bpm_min: float | None = None,
        bpm_max: float | None = None,
        mode: str | None = None,
    ) -> dict:
        # Current clean MVP behavior:
        # compose from precomputed DB analyses joined to track paths, then export.
        playlist = self.composer.compose(limit=limit)
        playlist_id = self._run_id_factory()

        if not isinstance(playlist_id, str) or not playlist_id.strip():
            raise RuntimeError("Pipeline run ID factory returned an invalid identifier")
        normalized_playlist_id = playlist_id.strip()

        export = self.exporter.export_m3u(
            playlist_id=normalized_playlist_id,
            tracks=playlist,
        )

        self._observe_composition(
            run_id=normalized_playlist_id,
            playlist=playlist,
            limit=limit,
            bpm_min=bpm_min,
            bpm_max=bpm_max,
            mode=mode,
        )

        return {
            "input": {
                "path": path,
                "limit": limit,
                "bpm_min": bpm_min,
                "bpm_max": bpm_max,
                "mode": mode,
            },
            "tracks": [track.track_id for track in playlist],
            "count": len(playlist),
            "export": export,
        }

    def _observe_composition(
        self,
        *,
        run_id: str,
        playlist: list,
        limit: int,
        bpm_min: float | None,
        bpm_max: float | None,
        mode: str | None,
    ) -> None:
        if not self._comparison_enabled or self._comparison_hook is None:
            return

        try:
            self._comparison_hook.observe(
                run_id=run_id,
                legacy_track_ids=tuple(track.track_id for track in playlist),
                target_track_count=limit,
                bpm_min=bpm_min,
                bpm_max=bpm_max,
                mode=mode,
            )
        except Exception:
            logger.warning(
                "composition comparison hook failed; legacy export preserved",
                exc_info=True,
            )
