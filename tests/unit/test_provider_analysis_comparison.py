from __future__ import annotations

from pathlib import Path

import services.analysis.provider_analysis_service as service_module
from core.analysis.contracts import CanonicalAnalysisResult
from core.analysis.provider_contracts import ProviderOutput
from data.models.analysis_record import AnalysisRecord
from data.models.canonical_analysis_record import (
    CanonicalAnalysisPersistenceRecord,
)
from services.analysis.provider_analysis_service import ProviderAnalysisService


class RecordingWriter:
    def __init__(self) -> None:
        self.records: list[CanonicalAnalysisPersistenceRecord] = []

    def upsert(self, record: CanonicalAnalysisPersistenceRecord) -> None:
        self.records.append(record)


class StaticLegacyReader:
    def __init__(self, record: AnalysisRecord | None) -> None:
        self.record = record

    def get_by_track_id(self, track_id: str) -> AnalysisRecord | None:
        assert track_id == "track-1"
        return self.record


class FailingLegacyReader:
    def get_by_track_id(self, track_id: str) -> AnalysisRecord | None:
        raise RuntimeError(f"read failed for {track_id}")


class RecordingSink:
    def __init__(self) -> None:
        self.receipts: list[object] = []

    def write(self, receipt: object) -> None:
        self.receipts.append(receipt)


def _output() -> ProviderOutput:
    normalized = CanonicalAnalysisResult(
        path="/tmp/test.wav",
        provider="baseline",
        bpm=120.0,
        bpm_confidence=0.8,
        key="A minor",
        energy=0.5,
        loudness_db=-12.0,
        duration_seconds=180.0,
        analysis_status="complete",
        analysis_version="canonical-mir-v1",
        source_analysis_version="0.1.0",
        provider_version="1",
        track_id="track-1",
    )
    return ProviderOutput(
        provider="baseline",
        backend="librosa",
        raw={},
        normalized=normalized,
    )


def _legacy() -> AnalysisRecord:
    return AnalysisRecord(
        track_id="track-1",
        analysis_version="0.1.0",
        features_version="0.1.0",
        extractor_backend="librosa",
        extractor_name="baseline",
        bpm=120.0,
        bpm_confidence=0.8,
        key="A",
        scale="minor",
        camelot="8A",
        energy=0.5,
        loudness_db=-12.0,
        duration_seconds=180.0,
    )


def test_successful_write_emits_one_comparison_receipt(
    monkeypatch: object,
) -> None:
    output = _output()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        service_module,
        "analyze_with_provider_selection",
        lambda **_: output,
    )
    writer = RecordingWriter()
    writer_sink = RecordingSink()
    comparison_sink = RecordingSink()
    service = ProviderAnalysisService(
        canonical_writer=writer,
        canonical_writer_is_enabled=True,
        receipt_sink=writer_sink,
        comparison_is_enabled=True,
        legacy_analysis_reader=StaticLegacyReader(_legacy()),
        comparison_receipt_sink=comparison_sink,
    )

    returned = service.analyze(track_id="track-1", path=Path("test.wav"))

    assert returned is output
    assert len(writer.records) == 1
    assert len(comparison_sink.receipts) == 1
    receipt = comparison_sink.receipts[0]
    assert receipt.outcome == "succeeded"


def test_missing_legacy_row_emits_skipped_receipt(
    monkeypatch: object,
) -> None:
    output = _output()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        service_module,
        "analyze_with_provider_selection",
        lambda **_: output,
    )
    comparison_sink = RecordingSink()
    service = ProviderAnalysisService(
        canonical_writer=RecordingWriter(),
        canonical_writer_is_enabled=True,
        receipt_sink=RecordingSink(),
        comparison_is_enabled=True,
        legacy_analysis_reader=StaticLegacyReader(None),
        comparison_receipt_sink=comparison_sink,
    )

    returned = service.analyze(track_id="track-1", path=Path("test.wav"))

    assert returned is output
    assert comparison_sink.receipts[0].outcome == "skipped"


def test_comparison_failure_does_not_change_provider_result(
    monkeypatch: object,
) -> None:
    output = _output()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        service_module,
        "analyze_with_provider_selection",
        lambda **_: output,
    )
    comparison_sink = RecordingSink()
    service = ProviderAnalysisService(
        canonical_writer=RecordingWriter(),
        canonical_writer_is_enabled=True,
        receipt_sink=RecordingSink(),
        comparison_is_enabled=True,
        legacy_analysis_reader=FailingLegacyReader(),
        comparison_receipt_sink=comparison_sink,
    )

    returned = service.analyze(track_id="track-1", path=Path("test.wav"))

    assert returned is output
    assert comparison_sink.receipts[0].outcome == "failed"
