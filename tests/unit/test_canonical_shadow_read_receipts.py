import json
import stat
from pathlib import Path

from core.analysis.canonical_legacy_comparison import (
    COMPARISON_SCHEMA_VERSION,
    CanonicalLegacyComparison,
)
from core.analysis.canonical_shadow_read_receipts import (
    CanonicalShadowReadReceipt,
    JsonlCanonicalShadowReadReceiptSink,
)


def test_jsonl_receipt_is_bounded_and_excludes_payloads(tmp_path: Path) -> None:
    comparison = CanonicalLegacyComparison(
        track_id="track-1",
        provider="baseline",
        legacy_analysis_version="legacy-v1",
        canonical_analysis_version="canonical-v1",
        comparison_schema_version=COMPARISON_SCHEMA_VERSION,
        fields=(),
    )
    receipt = CanonicalShadowReadReceipt.from_comparison(
        comparison,
        duration_ms=1.23456,
        correlation_id=" request-1 ",
    )
    path = tmp_path / "nested" / "receipts.jsonl"

    JsonlCanonicalShadowReadReceiptSink(path).write(receipt)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["event_name"] == "canonical_shadow_read_succeeded"
    assert payload["duration_ms"] == 1.235
    assert payload["correlation_id"] == "request-1"
    assert "path" not in payload
    assert "raw" not in payload
    assert "payload" not in payload
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_correlation_id_is_bounded() -> None:
    receipt = CanonicalShadowReadReceipt.canonical_missing(
        track_id="track-1",
        legacy_analysis_version="legacy-v1",
        duration_ms=0.0,
        correlation_id="x" * 256,
    )

    assert receipt.correlation_id == "x" * 128


def test_failed_receipt_contains_only_error_type() -> None:
    receipt = CanonicalShadowReadReceipt.failed(
        track_id="track-1",
        legacy_analysis_version="legacy-v1",
        duration_ms=-1.0,
        error_type="RuntimeError",
    )

    assert receipt.outcome == "failed"
    assert receipt.duration_ms == 0.0
    assert receipt.error_type == "RuntimeError"
    assert receipt.provider is None
    assert receipt.canonical_analysis_version is None
