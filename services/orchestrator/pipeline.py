from __future__ import annotations

import logging
from collections.abc import Callable

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
from services.orchestrator.composition_authority import (
    LegacyCompositionAuthority,
    PipelineCompositionAuthority,
    PipelineCompositionCommand,
    new_pipeline_run_id,
)


logger = logging.getLogger(__name__)


_new_pipeline_run_id = new_pipeline_run_id


class OrchestratorPipeline:
    def __init__(
        self,
        *,
        composition_authority: PipelineCompositionAuthority | None = None,
        composer: Composer | None = None,
        exporter: Exporter | None = None,
        run_id_factory: Callable[[], str] | None = None,
        comparison_hook: object | None = None,
        comparison_enabled: bool | None = None,
    ) -> None:
        if composition_authority is not None and any(
            value is not None for value in (composer, exporter, run_id_factory)
        ):
            raise ValueError(
                "composition_authority cannot be combined with legacy dependencies"
            )

        if composition_authority is None:
            legacy_authority = LegacyCompositionAuthority(
                composer=composer,
                exporter=exporter,
                run_id_factory=run_id_factory,
            )
            self._composition_authority = legacy_authority
            self.composer = legacy_authority.composer
            self.exporter = legacy_authority.exporter
        else:
            self._composition_authority = composition_authority
            self.composer = None
            self.exporter = None

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
        outcome = self._composition_authority.execute(
            PipelineCompositionCommand(
                path=path,
                limit=limit,
                bpm_min=bpm_min,
                bpm_max=bpm_max,
                mode=mode,
            )
        )
        playlist = list(outcome.tracks)
        export = dict(outcome.export)

        self._observe_composition(
            run_id=outcome.run_id,
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

        arguments = {
            "legacy_track_ids": tuple(track.track_id for track in playlist),
            "target_track_count": limit,
            "bpm_min": bpm_min,
            "bpm_max": bpm_max,
            "mode": mode,
        }

        try:
            observe_run = getattr(self._comparison_hook, "observe_run", None)
            if callable(observe_run):
                observe_run(run_id=run_id, **arguments)
                return

            observe = getattr(self._comparison_hook, "observe")
            observe(**arguments)
        except Exception:
            logger.warning(
                "composition comparison hook failed; legacy export preserved",
                exc_info=True,
            )
