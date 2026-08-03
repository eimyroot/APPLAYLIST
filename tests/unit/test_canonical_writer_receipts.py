from __future__ import annotations

import json
import stat
from pathlib import Path

from core.analysis.canonical_writer_receipts import (
    CanonicalWriterReceipt,
    JsonlCanonicalWriterReceiptSink,
)


def test_jsonl_sink_writes_auditable_receipt(tmp_path: Path) -> None:
    path = tmp_path / "receipts" / "writer.jsonl"
    sink = JsonlCanonicalWriterReceiptSink(path)
    receipt = CanonicalWriterReceipt.create(
        outcome="succeeded",
        duration_ms=12.3456,
        provider="baseline",
        canonical_analysis_version="canonical-mir-v1",
        track_id="track-1",
    )

    sink.write(receipt)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["event_name"] == "canonical_writer_shadow_write_succeeded"
    assert payload["duration_ms"] == 12.346
    assert "path" not in payload
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
