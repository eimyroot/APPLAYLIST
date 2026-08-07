from __future__ import annotations

import pytest

from core.analysis.canonical_shadow_read_receipts import (
    CanonicalShadowReadReceipt,
)
from data.models.analysis_record import AnalysisRecord
from data.models.canonical_analysis_record import (
    CanonicalAnalysisPersistenceRecord,
)
from services.analysis.canonical_shadow_reader import (
    CanonicalShadowReader,
    create_canonical_shadow_reader,
)


class RecordingCanonicalReader:
    def __init__(
        self,
        record: CanonicalAnalysisPersistenceRecord | None,
    ) -> None:
        self.record = record
        self.calls: list[str] = []

    def get(
        self,
        track_id: str,
    ) -> CanonicalAnalysisPersistenceRecord | None:
        self.calls.append(track_id)
        return self.record


class FailingCanonicalReader:
    def get(
        self,
        track_id: str,
    ) -> CanonicalAnalysisPersistenceRecord | None:
        raise RuntimeError(f"canonical read failed for {track_id}")


class RecordingSink:
    def __init__(self) -> None:
        self.receipts: list[CanonicalShadowReadReceipt] = []

    def write(self, receipt: CanonicalShadowReadReceipt) -> None:
        self.receipts.append(receipt)


class FailingSink:
    def write(self, receipt: CanonicalShadowReadReceipt) -> None:
        raise OSError(f"receipt unavailable for {receipt.track_id}")


def _legacy(*, bpm: float = 120.0) -> AnalysisRecord:
    return AnalysisRecord(
        track_id="track-1",
        analysis_version="legacy-v1",
        features_version="legacy-features-v1",
        extractor_backend="librosa",
        extractor_name="baseline",
        bpm=bpm,
        bpm_confidence=0.8,
        key="A",
        scale="minor",
        camelot="8A",
        energy=0.5,
        loudness_db=-12.0,
        duration_seconds=180.0,
    )


def _canonical(
    *,
    bpm: float = 120.0,
    track_id: str = "track-1",
) -> CanonicalAnalysisPersistenceRecord:
    return CanonicalAnalysisPersistenceRecord(
        track_id=track_id,
        provider="baseline",
        provider_version="1",
        canonical_analysis_version="canonical-v1",
        source_analysis_version="legacy-v1",
        bpm=bpm,
        bpm_confidence=0.8,
        key="A minor",
        key_confidence=None,
        key_system=None,
        energy=0.5,
        energy_confidence=None,
        loudness_db=-12.0,
        loudness_integrated_lufs=None,
        duration_seconds=180.0,
        sample_rate_hz=None,
        channels=None,
        genre_hint=None,
        analysis_status="complete",
        analyzed_at=None,
        warnings_json="[]",
    )


def test_disabled_observer_returns_same_legacy_object_without_dependencies() -> None:
    legacy = _legacy()
    observer = CanonicalShadowReader()

    returned = observer.observe_authoritative_legacy_read(legacy)

    assert returned is legacy
    assert observer.enabled is False


def test_enabled_observer_requires_canonical_reader() -> None:
    with pytest.raises(ValueError, match="canonical_reader"):
        CanonicalShadowReader(
            enabled=True,
            receipt_sink=RecordingSink(),
        )


def test_enabled_observer_requires_receipt_sink() -> None:
    with pytest.raises(ValueError, match="receipt_sink"):
        CanonicalShadowReader(
            enabled=True,
            canonical_reader=RecordingCanonicalReader(_canonical()),
        )


def test_matching_canonical_record_emits_succeeded_receipt() -> None:
    legacy = _legacy()
    reader = RecordingCanonicalReader(_canonical())
    sink = RecordingSink()
    ticks = iter((1_000_000, 2_500_000))
    observer = CanonicalShadowReader(
        canonical_reader=reader,
        enabled=True,
        receipt_sink=sink,
        monotonic_ns=lambda: next(ticks),
    )

    returned = observer.observe_authoritative_legacy_read(
        legacy,
        correlation_id="request-1",
    )

    assert returned is legacy
    assert reader.calls == ["track-1"]
    assert len(sink.receipts) == 1
    receipt = sink.receipts[0]
    assert receipt.outcome == "succeeded"
    assert receipt.duration_ms == 1.5
    assert receipt.correlation_id == "request-1"


def test_missing_canonical_record_emits_bounded_missing_receipt() -> None:
    legacy = _legacy()
    sink = RecordingSink()
    observer = CanonicalShadowReader(
        canonical_reader=RecordingCanonicalReader(None),
        enabled=True,
        receipt_sink=sink,
    )

    returned = observer.observe_authoritative_legacy_read(legacy)

    assert returned is legacy
    receipt = sink.receipts[0]
    assert receipt.outcome == "canonical_missing"
    assert receipt.provider is None
    assert receipt.matched_fields == ()
    assert receipt.mismatched_fields == ()


def test_divergent_canonical_record_emits_mismatch_receipt() -> None:
    legacy = _legacy()
    sink = RecordingSink()
    observer = CanonicalShadowReader(
        canonical_reader=RecordingCanonicalReader(_canonical(bpm=130.0)),
        enabled=True,
        receipt_sink=sink,
    )

    returned = observer.observe_authoritative_legacy_read(legacy)

    assert returned is legacy
    receipt = sink.receipts[0]
    assert receipt.outcome == "mismatch"
    assert "bpm" in receipt.mismatched_fields


def test_canonical_read_failure_does_not_change_legacy_result() -> None:
    legacy = _legacy()
    sink = RecordingSink()
    observer = CanonicalShadowReader(
        canonical_reader=FailingCanonicalReader(),
        enabled=True,
        receipt_sink=sink,
    )

    returned = observer.observe_authoritative_legacy_read(legacy)

    assert returned is legacy
    receipt = sink.receipts[0]
    assert receipt.outcome == "failed"
    assert receipt.error_type == "RuntimeError"


def test_identity_mismatch_is_observed_as_failure() -> None:
    legacy = _legacy()
    sink = RecordingSink()
    observer = CanonicalShadowReader(
        canonical_reader=RecordingCanonicalReader(
            _canonical(track_id="different-track")
        ),
        enabled=True,
        receipt_sink=sink,
    )

    returned = observer.observe_authoritative_legacy_read(legacy)

    assert returned is legacy
    receipt = sink.receipts[0]
    assert receipt.outcome == "failed"
    assert receipt.error_type == "ValueError"


def test_receipt_write_failure_does_not_change_legacy_result() -> None:
    legacy = _legacy()
    observer = CanonicalShadowReader(
        canonical_reader=RecordingCanonicalReader(_canonical()),
        enabled=True,
        receipt_sink=FailingSink(),
    )

    returned = observer.observe_authoritative_legacy_read(legacy)

    assert returned is legacy


def test_factory_is_default_off_and_does_not_create_product_read_path() -> None:
    observer = create_canonical_shadow_reader()
    legacy = _legacy()

    returned = observer.observe_authoritative_legacy_read(legacy)

    assert observer.enabled is False
    assert returned is legacy
