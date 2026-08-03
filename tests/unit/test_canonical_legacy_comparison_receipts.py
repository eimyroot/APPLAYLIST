from __future__ import annotations

import json
import stat
from pathlib import Path

from core.analysis.canonical_legacy_comparison import (
    CanonicalLegacyComparison,
    FieldComparison,
    FieldComparisonStatus,
)
from core.analysis.canonical_legacy_comparison_receipts import (
    CanonicalLegacyComparisonReceipt,
    JsonlCanonicalLegacyComparisonReceiptSink,
)


def test_jsonl_receipt_excludes_paths_and_raw_payloads(
    tmp_path: Path,
) -> None:
    comparison = CanonicalLegacyComparison(
        track_id="track-1",
        provider="baseline",
        legacy_analysis_version="0.1.0",
        canonical_analysis_version="canonical-mir-v1",
        comparison_schema_version="comparison-v1",
        fields=(
            FieldComparison(
                field="bpm",
                status=FieldComparisonStatus.EXACT_MATCH,
                legacy_value=120.0,
                canonical_value=120.0,
                absolute_delta=0.0,
            ),
        ),
    )
    receipt = CanonicalLegacyComparisonReceipt.from_comparison(
        comparison,
        duration_ms=1.2345,
    )
    path = tmp_path / "comparison.jsonl"

    JsonlCanonicalLegacyComparisonReceiptSink(path).write(receipt)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["event_name"] == (
        "canonical_legacy_comparison_succeeded"
    )
    assert payload["duration_ms"] == 1.234
    assert "path" not in payload
    assert "raw" not in payload
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
