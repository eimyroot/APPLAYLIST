from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from typing import Any

from core.analysis.benchmark_models import BenchmarkReference, BenchmarkResultRow


def classify_bpm(
    estimated: float | None,
    reference: float | None,
    *,
    alternate_references: Sequence[float] = (),
    tolerance: float = 0.01,
) -> tuple[str | None, float | None]:
    if reference is None:
        return None, None
    if estimated is None:
        return "missing", None

    references = (reference, *alternate_references)
    exact_error = min(_relative_error(estimated, target) for target in references)
    if exact_error <= tolerance:
        return "exact", exact_error * 100.0

    half_double_targets = tuple(
        target
        for value in references
        for target in (value / 2.0, value * 2.0)
    )
    half_double_error = min(
        _relative_error(estimated, target) for target in half_double_targets
    )
    if half_double_error <= tolerance:
        return "half_double", half_double_error * 100.0
    return "miss", min(exact_error, half_double_error) * 100.0


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
        expected_number,
        actual_number,
    ) == 1:
        return "adjacent"
    return "incompatible"


def spearman_rank_correlation(
    pairs: Sequence[tuple[float, float]],
) -> float | None:
    if len(pairs) < 2:
        return None
    references = [pair[0] for pair in pairs]
    estimates = [pair[1] for pair in pairs]
    left_ranks = _average_ranks(references)
    right_ranks = _average_ranks(estimates)
    left_mean = statistics.fmean(left_ranks)
    right_mean = statistics.fmean(right_ranks)
    numerator = sum(
        (left - left_mean) * (right - right_mean)
        for left, right in zip(left_ranks, right_ranks, strict=True)
    )
    left_variance = sum((value - left_mean) ** 2 for value in left_ranks)
    right_variance = sum((value - right_mean) ** 2 for value in right_ranks)
    denominator = math.sqrt(left_variance * right_variance)
    if denominator <= 0.0:
        return None
    return numerator / denominator


def summarize_rows(
    rows: Sequence[BenchmarkResultRow],
) -> tuple[dict[str, Any], dict[str, bool | None]]:
    attempted = len(rows)
    success_rows = [row for row in rows if row.status == "success"]
    controlled = sum(row.status == "controlled_failure" for row in rows)
    uncontrolled = sum(row.status == "uncontrolled_failure" for row in rows)

    bpm_rows = [row for row in success_rows if row.bpm_classification is not None]
    bpm_exact = sum(row.bpm_classification == "exact" for row in bpm_rows)
    bpm_half_double = sum(
        row.bpm_classification == "half_double" for row in bpm_rows
    )
    bpm_compatible_rate = (
        (bpm_exact + bpm_half_double) / len(bpm_rows) if bpm_rows else None
    )

    key_rows = [row for row in success_rows if row.key_classification is not None]
    key_exact = sum(row.key_classification == "exact" for row in key_rows)
    key_relative = sum(row.key_classification == "relative" for row in key_rows)
    key_adjacent = sum(row.key_classification == "adjacent" for row in key_rows)
    exact_key_rate = key_exact / len(key_rows) if key_rows else None
    compatible_key_rate = (
        (key_exact + key_relative + key_adjacent) / len(key_rows)
        if key_rows
        else None
    )

    energy_pairs = [
        (row.energy_reference_rank, row.energy_estimated)
        for row in success_rows
        if row.energy_reference_rank is not None and row.energy_estimated is not None
    ]
    energy_correlation = spearman_rank_correlation(energy_pairs)
    runtimes = sorted(row.runtime_ms for row in rows)
    decode_success_rate = len(success_rows) / attempted if attempted else 0.0

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
