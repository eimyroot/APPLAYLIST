from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import statistics
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from core.analysis.provider_contract import CanonicalAnalysisResult, ProviderContractError
from core.analysis.provider_service import RoutedAnalysisService
from core.analysis.providers import list_analyzer_providers, select_best_provider


MANIFEST_SCHEMA_VERSION = "applaylist-mir-benchmark-manifest-v1"
REPORT_SCHEMA_VERSION = "applaylist-mir-benchmark-report-v1"
_CAMELOT_PATTERN = re.compile(r"(?:[1-9]|1[0-2])[AB]")
_NOTE_NAMES = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"}


class BenchmarkManifestError(ValueError):
    """Raised when benchmark input cannot be trusted."""


class AnalysisService(Protocol):
    def analyze_path(
        self,
        path: str,
        *,
        preferred_provider: str | None = None,
    ) -> CanonicalAnalysisResult: ...


@dataclass(frozen=True, slots=True)
class BenchmarkReference:
    bpm: float | None = None
    alternate_bpms: tuple[float, ...] = ()
    key_tonic: str | None = None
    key_scale: str | None = None
    camelot: str | None = None
    energy_rank: float | None = None


@dataclass(frozen=True, slots=True)
class BenchmarkItem:
    item_id: str
    relative_path: str
    reference: BenchmarkReference


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    schema_version: str
    dataset_name: str
    dataset_version: str
    source: str
    license_id: str
    dataset_checksum: str
    dataset_root: str
    manifest_path: str
    manifest_sha256: str
    items: tuple[BenchmarkItem, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkResultRow:
    item_id: str
    relative_path: str
    status: str
    runtime_ms: float
    error_code: str | None
    error_message: str | None
    provider: str | None
    provider_version: str | None
    algorithm_version: str | None
    bpm_reference: float | None
    bpm_estimated: float | None
    bpm_classification: str | None
    bpm_error_percent: float | None
    key_reference: str | None
    key_estimated: str | None
    key_classification: str | None
    energy_reference_rank: float | None
    energy_estimated: float | None
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    schema_version: str
    generated_at: str
    source_commit: str
    preferred_provider: str | None
    manifest: dict[str, Any]
    environment: dict[str, Any]
    rows: tuple[BenchmarkResultRow, ...]
    summary: dict[str, Any]
    acceptance_gates: dict[str, bool | None]
    decision_status: str = "manual_review_required"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "source_commit": self.source_commit,
            "preferred_provider": self.preferred_provider,
            "manifest": self.manifest,
            "environment": self.environment,
            "rows": [asdict(row) for row in self.rows],
            "summary": self.summary,
            "acceptance_gates": self.acceptance_gates,
            "decision_status": self.decision_status,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )


def load_dataset_manifest(
    manifest_path: str | Path,
    *,
    dataset_root: str | Path,
) -> DatasetManifest:
    root = _absolute_directory(dataset_root, field="dataset_root")
    manifest_file = _absolute_file(manifest_path, field="manifest_path")

    raw_bytes = manifest_file.read_bytes()
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BenchmarkManifestError("manifest must be valid UTF-8 JSON") from exc
    if not isinstance(payload, Mapping):
        raise BenchmarkManifestError("manifest root must be an object")

    schema_version = _required_text(payload.get("schema_version"), "schema_version")
    if schema_version != MANIFEST_SCHEMA_VERSION:
        raise BenchmarkManifestError(
            f"unsupported manifest schema: {schema_version}"
        )

    dataset = payload.get("dataset")
    if not isinstance(dataset, Mapping):
        raise BenchmarkManifestError("dataset must be an object")

    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise BenchmarkManifestError("items must be a non-empty array")

    items: list[BenchmarkItem] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, Mapping):
            raise BenchmarkManifestError(f"items[{index}] must be an object")
        item_id = _required_text(raw_item.get("id"), f"items[{index}].id")
        if item_id in seen_ids:
            raise BenchmarkManifestError(f"duplicate benchmark item id: {item_id}")
        seen_ids.add(item_id)

        relative_path = _validated_relative_path(
            raw_item.get("path"),
            root=root,
            field=f"items[{index}].path",
        )
        if relative_path in seen_paths:
            raise BenchmarkManifestError(
                f"duplicate benchmark item path: {relative_path}"
            )
        seen_paths.add(relative_path)

        reference_payload = raw_item.get("reference")
        if not isinstance(reference_payload, Mapping):
            raise BenchmarkManifestError(
                f"items[{index}].reference must be an object"
            )
        reference = _parse_reference(reference_payload, index=index)
        if all(
            value is None or value == ()
            for value in (
                reference.bpm,
                reference.alternate_bpms,
                reference.camelot,
                reference.energy_rank,
            )
        ):
            raise BenchmarkManifestError(
                f"items[{index}] must provide BPM, key or energy reference"
            )

        items.append(
            BenchmarkItem(
                item_id=item_id,
                relative_path=relative_path,
                reference=reference,
            )
        )

    return DatasetManifest(
        schema_version=schema_version,
        dataset_name=_required_text(dataset.get("name"), "dataset.name"),
        dataset_version=_required_text(dataset.get("version"), "dataset.version"),
        source=_required_text(dataset.get("source"), "dataset.source"),
        license_id=_required_text(dataset.get("license"), "dataset.license"),
        dataset_checksum=_required_text(
            dataset.get("checksum"), "dataset.checksum"
        ),
        dataset_root=str(root),
        manifest_path=str(manifest_file),
        manifest_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        items=tuple(items),
    )


class MIRBenchmarkRunner:
    def __init__(
        self,
        *,
        analysis_service: AnalysisService | None = None,
        timer: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._analysis_service = analysis_service or RoutedAnalysisService()
        self._timer = timer

    def run(
        self,
        manifest: DatasetManifest,
        *,
        preferred_provider: str | None = "librosa",
        source_commit: str = "unknown",
        generated_at: str | None = None,
    ) -> BenchmarkReport:
        root = Path(manifest.dataset_root)
        rows: list[BenchmarkResultRow] = []

        for item in manifest.items:
            source = (root / item.relative_path).resolve(strict=True)
            started = self._timer()
            try:
                result = self._analysis_service.analyze_path(
                    str(source),
                    preferred_provider=preferred_provider,
                )
            except ProviderContractError as exc:
                elapsed = _elapsed_ms(started, self._timer())
                rows.append(
                    _failure_row(
                        item,
                        status="controlled_failure",
                        runtime_ms=elapsed,
                        error_code=getattr(exc, "code", "provider_error"),
                        error_message=str(exc),
                    )
                )
                continue
            except Exception as exc:  # benchmark must retain evidence of uncontrolled failures
                elapsed = _elapsed_ms(started, self._timer())
                rows.append(
                    _failure_row(
                        item,
                        status="uncontrolled_failure",
                        runtime_ms=elapsed,
                        error_code=f"uncontrolled:{type(exc).__name__}",
                        error_message=str(exc),
                    )
                )
                continue

            elapsed = _elapsed_ms(started, self._timer())
            bpm_classification, bpm_error = classify_bpm(
                result.bpm,
                item.reference.bpm,
                alternate_references=item.reference.alternate_bpms,
            )
            key_classification = classify_key(
                estimated_camelot=result.camelot,
                estimated_tonic=result.key_tonic,
                estimated_scale=result.key_scale,
                reference=item.reference,
            )
            rows.append(
                BenchmarkResultRow(
                    item_id=item.item_id,
                    relative_path=item.relative_path,
                    status="success",
                    runtime_ms=elapsed,
                    error_code=None,
                    error_message=None,
                    provider=result.provider,
                    provider_version=result.provider_version,
                    algorithm_version=result.algorithm_version,
                    bpm_reference=item.reference.bpm,
                    bpm_estimated=result.bpm,
                    bpm_classification=bpm_classification,
                    bpm_error_percent=bpm_error,
                    key_reference=_reference_key_label(item.reference),
                    key_estimated=result.camelot or result.key,
                    key_classification=key_classification,
                    energy_reference_rank=item.reference.energy_rank,
                    energy_estimated=result.energy,
                    warnings=result.warnings,
                )
            )

        summary, gates = _summarize(rows)
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
                "platform": platform.platform(),
                "machine": platform.machine(),
            },
            rows=tuple(rows),
            summary=summary,
            acceptance_gates=gates,
        )


def classify_bpm(
    estimated: float | None,
    reference: float | None,
    *,
    alternate_references: Sequence[float] = (),
    tolerance: float = 0.01,
) -> tuple[str | None, float | None]:
    if reference is None:
        return None, None
    references = (reference, *alternate_references)
    if estimated is None:
        return "missing", None

    best_exact_error = min(_relative_error(estimated, target) for target in references)
    if best_exact_error <= tolerance:
        return "exact", best_exact_error * 100.0

    half_double_targets = tuple(
        target
        for reference_value in references
        for target in (reference_value / 2.0, reference_value * 2.0)
    )
    best_half_double_error = min(
        _relative_error(estimated, target) for target in half_double_targets
    )
    if best_half_double_error <= tolerance:
        return "half_double", best_half_double_error * 100.0

    best_error = min(best_exact_error, best_half_double_error)
    return "miss", best_error * 100.0


def classify_key(
    *,
    estimated_camelot: str | None,
    estimated_tonic: str | None,
    estimated_scale: str | None,
    reference: BenchmarkReference,
) -> str | None:
    if reference.camelot is None and reference.key_tonic is None:
        return None
    if estimated_camelot is None and estimated_tonic is None:
        return "missing"

    if (
        reference.key_tonic is not None
        and reference.key_scale is not None
        and estimated_tonic == reference.key_tonic
        and estimated_scale == reference.key_scale
    ):
        return "exact"

    if reference.camelot is None or estimated_camelot is None:
        return "incompatible"

    expected = reference.camelot.upper()
    actual = estimated_camelot.upper()
    if actual == expected:
        return "exact"

    expected_number, expected_letter = int(expected[:-1]), expected[-1]
    actual_number, actual_letter = int(actual[:-1]), actual[-1]
    if expected_number == actual_number and expected_letter != actual_letter:
        return "relative"
    if expected_letter == actual_letter and _camelot_distance(
        expected_number, actual_number
    ) == 1:
        return "adjacent"
    return "incompatible"


def spearman_rank_correlation(pairs: Sequence[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None
    references = [pair[0] for pair in pairs]
    estimates = [pair[1] for pair in pairs]
    reference_ranks = _average_ranks(references)
    estimate_ranks = _average_ranks(estimates)
    mean_reference = statistics.fmean(reference_ranks)
    mean_estimate = statistics.fmean(estimate_ranks)
    numerator = sum(
        (left - mean_reference) * (right - mean_estimate)
        for left, right in zip(reference_ranks, estimate_ranks, strict=True)
    )
    left_variance = sum((value - mean_reference) ** 2 for value in reference_ranks)
    right_variance = sum((value - mean_estimate) ** 2 for value in estimate_ranks)
    denominator = math.sqrt(left_variance * right_variance)
    if denominator <= 0.0:
        return None
    return numerator / denominator


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
    rows: list[dict[str, Any]] = []
    available = {key: asdict(value) for key, value in list_analyzer_providers().items()}
    provider = select_best_provider(provider_name)
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
        "summary": {"count": len(rows), "avg_runtime_ms": round(average, 3)},
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


def _parse_reference(payload: Mapping[str, Any], *, index: int) -> BenchmarkReference:
    bpm = _optional_positive_float(payload.get("bpm"), f"items[{index}].reference.bpm")
    raw_alternates = payload.get("alternate_bpms", [])
    if not isinstance(raw_alternates, list):
        raise BenchmarkManifestError(
            f"items[{index}].reference.alternate_bpms must be an array"
        )
    alternate_bpms = tuple(
        _required_positive_float(
            value, f"items[{index}].reference.alternate_bpms[{position}]"
        )
        for position, value in enumerate(raw_alternates)
    )

    key_payload = payload.get("key")
    if key_payload is None:
        key_payload = {}
    if not isinstance(key_payload, Mapping):
        raise BenchmarkManifestError(
            f"items[{index}].reference.key must be an object"
        )
    tonic = _optional_text(key_payload.get("tonic"), f"items[{index}].reference.key.tonic")
    if tonic is not None:
        tonic = tonic.upper()
        if tonic not in _NOTE_NAMES:
            raise BenchmarkManifestError(f"unsupported key tonic: {tonic}")
    scale = _optional_text(key_payload.get("scale"), f"items[{index}].reference.key.scale")
    if scale is not None:
        scale = scale.lower()
        if scale not in {"major", "minor"}:
            raise BenchmarkManifestError("key scale must be major or minor")
    if (tonic is None) != (scale is None):
        raise BenchmarkManifestError("key tonic and scale must be provided together")

    camelot = _optional_text(
        key_payload.get("camelot"), f"items[{index}].reference.key.camelot"
    )
    if camelot is not None:
        camelot = camelot.upper()
        if _CAMELOT_PATTERN.fullmatch(camelot) is None:
            raise BenchmarkManifestError(f"invalid Camelot key: {camelot}")

    return BenchmarkReference(
        bpm=bpm,
        alternate_bpms=alternate_bpms,
        key_tonic=tonic,
        key_scale=scale,
        camelot=camelot,
        energy_rank=_optional_finite_float(
            payload.get("energy_rank"),
            f"items[{index}].reference.energy_rank",
        ),
    )


def _summarize(
    rows: Sequence[BenchmarkResultRow],
) -> tuple[dict[str, Any], dict[str, bool | None]]:
    attempted = len(rows)
    success_rows = [row for row in rows if row.status == "success"]
    controlled = sum(row.status == "controlled_failure" for row in rows)
    uncontrolled = sum(row.status == "uncontrolled_failure" for row in rows)

    bpm_rows = [row for row in success_rows if row.bpm_classification is not None]
    bpm_exact = sum(row.bpm_classification == "exact" for row in bpm_rows)
    bpm_half_double = sum(row.bpm_classification == "half_double" for row in bpm_rows)

    key_rows = [row for row in success_rows if row.key_classification is not None]
    key_exact = sum(row.key_classification == "exact" for row in key_rows)
    key_relative = sum(row.key_classification == "relative" for row in key_rows)
    key_adjacent = sum(row.key_classification == "adjacent" for row in key_rows)

    energy_pairs = [
        (row.energy_reference_rank, row.energy_estimated)
        for row in success_rows
        if row.energy_reference_rank is not None and row.energy_estimated is not None
    ]
    energy_correlation = spearman_rank_correlation(energy_pairs)
    runtimes = sorted(row.runtime_ms for row in rows)

    decode_success_rate = len(success_rows) / attempted if attempted else 0.0
    bpm_compatible_rate = (
        (bpm_exact + bpm_half_double) / len(bpm_rows) if bpm_rows else None
    )
    exact_key_rate = key_exact / len(key_rows) if key_rows else None
    compatible_key_rate = (
        (key_exact + key_relative + key_adjacent) / len(key_rows)
        if key_rows
        else None
    )

    summary = {
        "attempted": attempted,
        "succeeded": len(success_rows),
        "controlled_failures": controlled,
        "uncontrolled_failures": uncontrolled,
        "decode_success_rate": decode_success_rate,
        "bpm": {
            "evaluated": len(bpm_rows),
            "exact": bpm_exact,
            "half_double": bpm_half_double,
            "miss": sum(row.bpm_classification == "miss" for row in bpm_rows),
            "compatible_rate": bpm_compatible_rate,
        },
        "key": {
            "evaluated": len(key_rows),
            "exact": key_exact,
            "relative": key_relative,
            "adjacent": key_adjacent,
            "incompatible": sum(
                row.key_classification == "incompatible" for row in key_rows
            ),
            "exact_rate": exact_key_rate,
            "compatible_rate": compatible_key_rate,
        },
        "energy": {
            "evaluated": len(energy_pairs),
            "spearman_rank_correlation": energy_correlation,
        },
        "runtime_ms": {
            "median": statistics.median(runtimes) if runtimes else 0.0,
            "p95": _percentile(runtimes, 0.95),
        },
    }
    gates: dict[str, bool | None] = {
        "decode_success_at_least_99_5_percent": decode_success_rate >= 0.995,
        "no_uncontrolled_failures": uncontrolled == 0,
        "bpm_half_double_compatible_at_least_95_percent": (
            bpm_compatible_rate >= 0.95 if bpm_compatible_rate is not None else None
        ),
        "exact_key_at_least_75_percent": (
            exact_key_rate >= 0.75 if exact_key_rate is not None else None
        ),
        "camelot_compatible_key_at_least_90_percent": (
            compatible_key_rate >= 0.90 if compatible_key_rate is not None else None
        ),
        "energy_rank_correlation_at_least_0_75": (
            energy_correlation >= 0.75 if energy_correlation is not None else None
        ),
    }
    return summary, gates


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
        bpm_classification="missing" if item.reference.bpm is not None else None,
        bpm_error_percent=None,
        key_reference=_reference_key_label(item.reference),
        key_estimated=None,
        key_classification=(
            "missing"
            if item.reference.camelot is not None or item.reference.key_tonic is not None
            else None
        ),
        energy_reference_rank=item.reference.energy_rank,
        energy_estimated=None,
        warnings=(),
    )


def _reference_key_label(reference: BenchmarkReference) -> str | None:
    if reference.camelot is not None:
        return reference.camelot
    if reference.key_tonic is not None and reference.key_scale is not None:
        return f"{reference.key_tonic} {reference.key_scale}"
    return None


def _absolute_directory(path: str | Path, *, field: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise BenchmarkManifestError(f"{field} must be absolute")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise BenchmarkManifestError(f"{field} cannot be resolved") from exc
    if not resolved.is_dir():
        raise BenchmarkManifestError(f"{field} must be a directory")
    return resolved


def _absolute_file(path: str | Path, *, field: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise BenchmarkManifestError(f"{field} must be absolute")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise BenchmarkManifestError(f"{field} cannot be resolved") from exc
    if not resolved.is_file():
        raise BenchmarkManifestError(f"{field} must be a regular file")
    return resolved


def _validated_relative_path(value: Any, *, root: Path, field: str) -> str:
    text = _required_text(value, field)
    candidate = Path(text)
    if candidate.is_absolute():
        raise BenchmarkManifestError(f"{field} must be relative to dataset_root")
    try:
        resolved = (root / candidate).resolve(strict=True)
        relative = resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise BenchmarkManifestError(f"{field} escapes or is missing from dataset_root") from exc
    if not resolved.is_file():
        raise BenchmarkManifestError(f"{field} must reference a regular file")
    return relative.as_posix()


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkManifestError(f"{field} must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > 512:
        raise BenchmarkManifestError(f"{field} is too long")
    return normalized


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field)


def _required_positive_float(value: Any, field: str) -> float:
    parsed = _optional_positive_float(value, field)
    if parsed is None:
        raise BenchmarkManifestError(f"{field} must be a positive number")
    return parsed


def _optional_positive_float(value: Any, field: str) -> float | None:
    parsed = _optional_finite_float(value, field)
    if parsed is not None and parsed <= 0.0:
        raise BenchmarkManifestError(f"{field} must be positive")
    return parsed


def _optional_finite_float(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise BenchmarkManifestError(f"{field} must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise BenchmarkManifestError(f"{field} must be numeric") from exc
    if not math.isfinite(parsed):
        raise BenchmarkManifestError(f"{field} must be finite")
    return parsed


def _relative_error(value: float, target: float) -> float:
    return abs(value - target) / max(abs(target), 1e-12)


def _camelot_distance(left: int, right: int) -> int:
    direct = abs(left - right)
    return min(direct, 12 - direct)


def _average_ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda pair: pair[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average_rank = ((index + 1) + end) / 2.0
        for position in range(index, end):
            ranks[ordered[position][0]] = average_rank
        index = end
    return ranks


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def _elapsed_ms(started: float, finished: float) -> float:
    elapsed = (finished - started) * 1000.0
    return round(max(0.0, elapsed), 3)
