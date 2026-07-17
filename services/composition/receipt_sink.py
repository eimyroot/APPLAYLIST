from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from services.composition.receipt import CompositionComparisonReceipt


_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(slots=True)
class JsonCompositionReceiptSink:
    directory: Path

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def emit(self, receipt: CompositionComparisonReceipt) -> None:
        if _SAFE_RUN_ID.fullmatch(receipt.run_id) is None:
            raise ValueError("run_id contains unsafe characters")

        root = self.directory.resolve()
        root.mkdir(parents=True, exist_ok=True)
        target = root / f"{receipt.run_id}.json"
        if target.parent != root:
            raise ValueError("receipt target escaped configured directory")

        temporary = root / f".{receipt.run_id}.{uuid4().hex}.tmp"
        payload = json.dumps(
            receipt.to_dict(),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )

        try:
            temporary.write_text(payload + "\n", encoding="utf-8")
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise


@dataclass(slots=True)
class CompositeCompositionReceiptSink:
    sinks: tuple[object, ...]

    def emit(self, receipt: CompositionComparisonReceipt) -> None:
        errors: list[Exception] = []
        for sink in self.sinks:
            try:
                sink.emit(receipt)
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise RuntimeError(
                f"{len(errors)} composition receipt sink(s) failed"
            ) from errors[0]
