from __future__ import annotations

import json
import platform
import statistics
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.analysis.benchmark_metrics import (
    classify_bpm,
    classify_key,
    summarize_rows,
)
from core.analysis.benchmark_models import (
    REPORT_SCHEMA_VERSION,
    AnalysisService,
    BenchmarkItem,
    BenchmarkReport,
    BenchmarkResultRow,
    DatasetManifest,
)
from core.analysis.provider_contract import ProviderContractError
from core.analysis.provider_service import RoutedAnalysisService
from core.analysis.providers import list_analyzer_providers, select_best_provider


class MIRBenchmarkRunner:
    def __init__(
        self,
        *,
        analysis_service: AnalysisService | None = None,
        timer: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._analysis_service = (
            analysis_service if analysis_service is not None else RoutedAnalysisService()
        )
        self._timer = timer

    def run(
        self,
        manifest: DatasetManifest,
        *,
        preferred_provider: str | None = "librosa",
        source_commit: str = "unknown",
        generated_at: str | None = None,
    ) -> BenchmarkReport:
        root = Path(manifest.dataset_root).resolve(strict=True)
        rows: list[BenchmarkResultRow] = []

        for item in manifest.items:
            try:
                source = _resolve_item_source(root, item)
            except Exception as exc:
                rows.append(
                    _failure_row(
                        item,
                        status="uncontrolled_failure",
                        runtime_ms=0.0,
                        error_code=f"dataset_source_invalid:{type(exc).__name__}",
                        error_message=str(exc),
                    )
                )
                continue

            started = self._timer()
            try:
                result = self._analysis_service.analyze_path(
                    str(source),
                    preferred_provider=preferred_provider,
                )
            except ProviderContractError as exc:
                rows.append(
                    _failure_row(
                        item,
                        status="controlled_failure",
                        runtime_ms=_elapsed_ms(started, self._timer()),
                        error_code=getattr(exc, "code", "provider_error"),
                        error_message=str(exc),
                    )
                )
                continue
            except Exception as exc:
                rows.append(
                    _failure_row(
                        item,
                        status="uncontrolled_failure",
                        runtime_ms=_elapsed_ms(started, self._timer()),
                        error_code=f"uncontrolled:{type(exc).__name__}",
                        error_message=str(exc),
                    )
                )
                continue

            bpm_classification, bpm_error = classify_bpm(
                result.bpm,
                item.reference.bpm,
                alternate_references=item.reference.alternate_bpms,
            )
            rows.append(
                BenchmarkResultRow(
                    item_id=item.item_id,
                    relative_path=item.relative_path,
                    status="success",
                    runtime_ms=_elapsed_ms(started, self._timer()),
                    error_code=None,
                    error_message=None,
                    provider=result.provider,
                    provider_version=result.provider_version,
                    algorithm_version=result.algorithm_version,
                    bpm_reference=item.reference.bpm,
                    bpm_estimated=result.bpm,
                    bpm_classification=bpm_classification,
                    bpm_error_percent=bpm_error,
                    key_reference=_reference_key_label(item),
                    key_estimated=result.camelot or result.key,
                    key_classification=classify_key(
                        estimated_camelot=result.camelot,
                        estimated_tonic=result.key_tonic,
                        estimated_scale=result.key_scale,
                        reference=item.reference,
                    ),
                    energy_reference_rank=item.reference.energy_rank,
                    energy_estimated=result.energy,
                    warnings=result.warnings,
                )
            )

        summary, gates = summarize_rows(rows)
        return BenchmarkReport(
            schema_version=REPORT_SCHEMA_VERSION,
            generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
            source_commit=_required_text(source_commit, "source_commit"),
            preferred_provider=preferred_provider,
            manifest={
                "schema_version": manifest.schema_version,
                "dataset_name": manifest.dataset_name,
                "dataset_version": manifest.dataset_version,
                "source": manifest.source,
                "license": manifest.license_id,
                "dataset_checksum": manifest.dataset_checksum,
                "manifest_sha256": manifest.manifest_sha256,
                "item_count": len(manifest.items),
            },
            environment={
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
                "executable": sys.executable,
                "platform": platform.platform(),
                "machine": platform.machine(),
            },
            rows=tuple(rows),
            summary=summary,
            acceptance_gates=gates,
        )


def write_benchmark_report(report: BenchmarkReport, output_path: str | Path) -> Path:
    output = Path(output_path)
    if not output.is_absolute():
        raise ValueError("benchmark output path must be absolute")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(report.to_json() + "\n", encoding="utf-8")
    temporary.replace(output)
    return output


def benchmark_paths(
    paths: Iterable[str],
    provider_name: str | None = None,
) -> dict[str, Any]:
    """Compatibility timer helper retained for pre-Bundle-46 callers."""
    available = {
        key: asdict(value) for key, value in list_analyzer_providers().items()
    }
    provider = select_best_provider(provider_name)
    rows: list[dict[str, Any]] = []
    for raw_path in paths:
        path = str(Path(raw_path))
        started = time.perf_counter()
        result = provider.analyze(path)
        rows.append(
            {
                "path": path,
                "provider": result.get("provider", provider.name),
                "runtime_ms": _elapsed_ms(started, time.perf_counter()),
                "status": result.get("status", "unknown"),
            }
        )
    average = statistics.fmean(row["runtime_ms"] for row in rows) if rows else 0.0
    return {
        "provider_selected": provider.name,
        "providers": available,
        "rows": rows,
        "summary": {
            "count": len(rows),
            "avg_runtime_ms": round(average, 3),
        },
    }


def benchmark_to_json(
    paths: Iterable[str],
    provider_name: str | None = None,
) -> str:
    return json.dumps(
        benchmark_paths(paths, provider_name=provider_name),
        indent=2,
        ensure_ascii=False,
    )


def _resolve_item_source(root: Path, item: BenchmarkItem) -> Path:
    source = (root / item.relative_path).resolve(strict=True)
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise ValueError("benchmark source escaped dataset root") from exc
    if not source.is_file():
        raise ValueError("benchmark source must remain a regular file")
    return source


def _failure_row(
    item: BenchmarkItem,
    *,
    status: str,
    runtime_ms: float,
    error_code: str,
    error_message: str,
) -> BenchmarkResultRow:
    return BenchmarkResultRow(
        item_id=item.item_id,
        relative_path=item.relative_path,
        status=status,
        runtime_ms=runtime_ms,
        error_code=error_code,
        error_message=error_message,
        provider=None,
        provider_version=None,
        algorithm_version=None,
        bpm_reference=item.reference.bpm,
        bpm_estimated=None,
        bpm_classification=(
            "missing" if item.reference.bpm is not None else None
        ),
        bpm_error_percent=None,
        key_reference=_reference_key_label(item),
        key_estimated=None,
        key_classification=(
            "missing"
            if item.reference.camelot is not None
            or item.reference.key_tonic is not None
            else None
        ),
        energy_reference_rank=item.reference.energy_rank,
        energy_estimated=None,
        warnings=(),
    )


def _reference_key_label(item: BenchmarkItem) -> str | None:
    reference = item.reference
    if reference.camelot is not None:
        return reference.camelot
    if reference.key_tonic is not None and reference.key_scale is not None:
        return f"{reference.key_tonic} {reference.key_scale}"
    return None


def _required_text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _elapsed_ms(started: float, finished: float) -> float:
    return round(max(0.0, (finished - started) * 1000.0), 3)
