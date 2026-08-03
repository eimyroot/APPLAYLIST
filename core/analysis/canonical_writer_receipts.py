from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True)
class CanonicalWriterReceipt:
    event_name: str
    attempt_id: str
    outcome: str
    duration_ms: float
    provider: str
    canonical_analysis_version: str
    track_id: str | None
    error_type: str | None
    recorded_at: str

    @classmethod
    def create(
        cls,
        *,
        outcome: str,
        duration_ms: float,
        provider: str,
        canonical_analysis_version: str,
        track_id: str | None,
        error_type: str | None = None,
    ) -> CanonicalWriterReceipt:
        return cls(
            event_name=f"canonical_writer_shadow_write_{outcome}",
            attempt_id=str(uuid4()),
            outcome=outcome,
            duration_ms=round(max(0.0, duration_ms), 3),
            provider=provider,
            canonical_analysis_version=canonical_analysis_version,
            track_id=track_id,
            error_type=error_type,
            recorded_at=datetime.now(UTC).isoformat(),
        )


class CanonicalWriterReceiptSink(Protocol):
    def write(self, receipt: CanonicalWriterReceipt) -> None:
        ...


class JsonlCanonicalWriterReceiptSink:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser()

    def write(self, receipt: CanonicalWriterReceipt) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            asdict(receipt),
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"
        descriptor = os.open(
            self._path,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        try:
            os.write(descriptor, payload.encode("utf-8"))
        finally:
            os.close(descriptor)
