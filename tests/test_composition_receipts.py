from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from services.composition.adapter import CandidateIssue, CandidateIssueCode, CandidateIssueSeverity
from services.composition.hook import PipelineCompositionComparisonHook
from services.composition.models import CompositionStatus
from services.composition.receipt import build_composition_comparison_receipt
from services.composition.receipt_sink import CompositeCompositionReceiptSink, JsonCompositionReceiptSink
from services.composition.shadow import CompositionShadowReport


FIXED_TIME = datetime(2026, 7, 17, 5, 0, tzinfo=timezone.utc)


def sample_report() -> CompositionShadowReport:
    return CompositionShadowReport(
        legacy_track_ids=("legacy-1", "legacy-2"),
        canonical_track_ids=("legacy-2",),
        canonical_status=CompositionStatus.PARTIAL,
        canonical_failure_reason=None,
        candidate_count=3,
        adapted_count=2,
        rejected_count=1,
        fallback_count=1,
        overlap_count=1,
        position_match_count=0,
        legacy_coverage_ratio=0.5,
        canonical_coverage_ratio=1.0,
        adaptation_issues=(
            CandidateIssue("bad-track", CandidateIssueCode.INVALID_BPM, CandidateIssueSeverity.REJECTED),
            CandidateIssue("legacy-2", CandidateIssueCode.DURATION_FALLBACK, CandidateIssueSeverity.FALLBACK),
        ),
        canonical_warnings=("target track count not reached",),
    )


def build_receipt(run_id: str = "pipeline-test"):
    return build_composition_comparison_receipt(
        run_id=run_id,
        generated_at=FIXED_TIME,
        target_track_count=2,
        bpm_min=126.0,
        bpm_max=132.0,
        mode="club",
        report=sample_report(),
    )


def test_receipt_is_stable_and_json_safe() -> None:
    payload = build_receipt().to_dict()
    assert payload["schema_version"] == "1.0"
    assert payload["run_id"] == "pipeline-test"
    assert payload["generated_at"] == "2026-07-17T05:00:00Z"
    assert payload["quality"]["adaptation_issues"][0] == {
        "track_id": "bad-track",
        "code": "invalid_bpm",
        "severity": "rejected",
    }
    json.dumps(payload)


def test_receipt_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_composition_comparison_receipt(
            run_id="pipeline-test",
            generated_at=datetime(2026, 7, 17, 5, 0),
            target_track_count=2,
            bpm_min=126.0,
            bpm_max=132.0,
            mode="club",
            report=sample_report(),
        )


def test_json_sink_writes_atomically(tmp_path) -> None:
    directory = tmp_path / "receipts"
    JsonCompositionReceiptSink(directory).emit(build_receipt())
    target = directory / "pipeline-test.json"
    assert json.loads(target.read_text(encoding="utf-8"))["run_id"] == "pipeline-test"
    assert list(directory.glob("*.tmp")) == []
    assert list(directory.glob(".*.tmp")) == []


@pytest.mark.parametrize("run_id", ["bad id", "bad?query", ".hidden"])
def test_json_sink_rejects_unsafe_run_ids(tmp_path, run_id: str) -> None:
    with pytest.raises(ValueError, match="unsafe"):
        JsonCompositionReceiptSink(tmp_path).emit(build_receipt(run_id))


class RecordingSink:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.receipts = []

    def emit(self, receipt) -> None:
        self.receipts.append(receipt)
        if self.fail:
            raise RuntimeError("sink failed")


def test_composite_sink_attempts_every_sink() -> None:
    first = RecordingSink(fail=True)
    second = RecordingSink()
    receipt = build_receipt()
    with pytest.raises(RuntimeError, match="1 composition receipt sink"):
        CompositeCompositionReceiptSink((first, second)).emit(receipt)
    assert first.receipts == [receipt]
    assert second.receipts == [receipt]


class StaticComparisonService:
    def compare(self, request) -> CompositionShadowReport:
        return sample_report()


def test_hook_correlates_receipt_with_run_id() -> None:
    sink = RecordingSink()
    hook = PipelineCompositionComparisonHook(
        service=StaticComparisonService(),
        sink=sink,
        clock=lambda: FIXED_TIME,
    )
    receipt = hook.observe(
        run_id="pipeline-correlated",
        legacy_track_ids=("legacy-1", "legacy-2"),
        target_track_count=2,
        bpm_min=126.0,
        bpm_max=132.0,
        mode="club",
    )
    assert receipt.run_id == "pipeline-correlated"
    assert sink.receipts == [receipt]
