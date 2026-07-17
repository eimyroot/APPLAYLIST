from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.analysis.benchmark_models import (
    MANIFEST_SCHEMA_VERSION,
    BenchmarkItem,
    BenchmarkManifestError,
    BenchmarkReference,
    DatasetManifest,
)


_CAMELOT_PATTERN = re.compile(r"(?:[1-9]|1[0-2])[AB]")
_NOTE_NAMES = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"}


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
        raise BenchmarkManifestError(f"unsupported manifest schema: {schema_version}")

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
                reference.key_tonic,
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
        dataset_checksum=_required_text(dataset.get("checksum"), "dataset.checksum"),
        dataset_root=str(root),
        manifest_path=str(manifest_file),
        manifest_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        items=tuple(items),
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
            value,
            f"items[{index}].reference.alternate_bpms[{position}]",
        )
        for position, value in enumerate(raw_alternates)
    )

    key_payload = payload.get("key") or {}
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
        key_payload.get("camelot"),
        f"items[{index}].reference.key.camelot",
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
        raise BenchmarkManifestError(
            f"{field} escapes or is missing from dataset_root"
        ) from exc
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
