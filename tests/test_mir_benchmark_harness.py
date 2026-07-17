from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from core.analysis.benchmark import (
    BenchmarkManifestError,
    BenchmarkReference,
    MIRBenchmarkRunner,
    classify_bpm,
    classify_key,
    load_dataset_manifest,
    spearman_rank_correlation,
    write_benchmark_report,
)
from core.analysis.provider_contract import CanonicalAnalysisResult, ProviderRuntimeFailure


SAMPLE_RATE = 22_050


def _write_click_chord(path: Path, *, duration: float = 6.0, bpm: float = 120.0) -> None:
    sample_count = int(SAMPLE_RATE * duration)
    times = np.arange(sample_count, dtype=np.float64) / SAMPLE_RATE
    chord = (
        np.sin(2.0 * np.pi * 261.6256 * times)
        + np.sin(2.0 * np.pi * 329.6276 * times)
        + np.sin(2.0 * np.pi * 391.9954 * times)
    ) / 3.0
    chord *= 0.25

    clicks = np.zeros(sample_count, dtype=np.float64)
    pulse_length = int(SAMPLE_RATE * 0.03)
    pulse = np.hanning(pulse_length) * 0.75
    period = int(round(SAMPLE_RATE * 60.0 / bpm))
    for start in range(0, sample_count, period):
        end = min(sample_count, start + pulse_length)
        clicks[start:end] += pulse[: end - start]

    sf.write(path, np.clip(chord + clicks, -0.98, 0.98).astype(np.float32), SAMPLE_RATE)


def _manifest_payload(*, item_path: str = "track.wav", duplicate_id: bool = False) -> dict:
    items = [
        {
            "id": "track-1",
            "path": item_path,
            "reference": {
                "bpm": 120.0,
                "alternate_bpms": [60.0],
                "key": {"tonic": "C", "scale": "major", "camelot": "8B"},
                "energy_rank": 1.0,
            },
        }
    ]
    if duplicate_id:
        items.append(
            {
                "id": "track-1",
                "path": "other.wav",
                "reference": {"bpm": 128.0},
            }
        )
    return {
        "schema_version": "applaylist-mir-benchmark-manifest-v1",
        "dataset": {
            "name": "synthetic-test",
            "version": "1",
            "source": "locally generated test fixtures",
            "license": "test-only",
            "checksum": "sha256:test-dataset",
        },
        "items": items,
    }


def _write_manifest(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _canonical_result(path: str, **overrides) -> CanonicalAnalysisResult:
    values = {
        "path": path,
        "provider": "fake",
        "bpm": 120.0,
        "bpm_confidence": 0.9,
        "key": "8B",
        "key_confidence": 0.8,
        "energy": 0.4,
        "loudness_db": -10.0,
        "duration_seconds": 180.0,
        "genre_hint": None,
        "key_tonic": "C",
        "key_scale": "major",
        "camelot": "8B",
        "beat_stability": 0.9,
        "harmonic_ratio": 0.6,
        "percussive_ratio": 0.4,
        "provider_version": "1.0",
        "algorithm_version": "fake-v1",
        "warnings": (),
    }
    values.update(overrides)
    return CanonicalAnalysisResult(**values)


def test_manifest_loads_valid_external_dataset(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    track = dataset / "track.wav"
    track.write_bytes(b"audio")
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, _manifest_payload())

    manifest = load_dataset_manifest(
        manifest_path.resolve(),
        dataset_root=dataset.resolve(),
    )

    assert manifest.dataset_name == "synthetic-test"
    assert manifest.dataset_root == str(dataset.resolve())
    assert manifest.items[0].relative_path == "track.wav"
    assert manifest.items[0].reference.camelot == "8B"
    assert len(manifest.manifest_sha256) == 64


def test_manifest_rejects_path_escape_and_duplicate_ids(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    outside = tmp_path / "outside.wav"
    outside.write_bytes(b"audio")
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, _manifest_payload(item_path="../outside.wav"))

    with pytest.raises(BenchmarkManifestError, match="escapes or is missing"):
        load_dataset_manifest(manifest_path.resolve(), dataset_root=dataset.resolve())

    (dataset / "track.wav").write_bytes(b"audio")
    (dataset / "other.wav").write_bytes(b"audio")
    _write_manifest(manifest_path, _manifest_payload(duplicate_id=True))

    with pytest.raises(BenchmarkManifestError, match="duplicate benchmark item id"):
        load_dataset_manifest(manifest_path.resolve(), dataset_root=dataset.resolve())


def test_manifest_requires_absolute_paths_and_reference_data(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "track.wav").write_bytes(b"audio")
    manifest_path = tmp_path / "manifest.json"
    payload = _manifest_payload()
    payload["items"][0]["reference"] = {}
    _write_manifest(manifest_path, payload)

    with pytest.raises(BenchmarkManifestError, match="must be absolute"):
        load_dataset_manifest("manifest.json", dataset_root=dataset.resolve())

    with pytest.raises(BenchmarkManifestError, match="must provide BPM, key or energy"):
        load_dataset_manifest(manifest_path.resolve(), dataset_root=dataset.resolve())


def test_bpm_classification_is_half_double_aware() -> None:
    assert classify_bpm(120.0, 120.0)[0] == "exact"
    assert classify_bpm(60.0, 120.0)[0] == "half_double"
    assert classify_bpm(240.0, 120.0)[0] == "half_double"
    assert classify_bpm(121.5, 120.0)[0] == "miss"
    assert classify_bpm(None, 120.0) == ("missing", None)
    assert classify_bpm(120.0, None) == (None, None)


def test_key_classification_uses_camelot_relationships() -> None:
    reference = BenchmarkReference(
        key_tonic="C",
        key_scale="major",
        camelot="8B",
    )

    assert classify_key(
        estimated_camelot="8B",
        estimated_tonic="C",
        estimated_scale="major",
        reference=reference,
    ) == "exact"
    assert classify_key(
        estimated_camelot="8A",
        estimated_tonic="A",
        estimated_scale="minor",
        reference=reference,
    ) == "relative"
    assert classify_key(
        estimated_camelot="9B",
        estimated_tonic="G",
        estimated_scale="major",
        reference=reference,
    ) == "adjacent"
    assert classify_key(
        estimated_camelot="12A",
        estimated_tonic="C#",
        estimated_scale="minor",
        reference=reference,
    ) == "incompatible"


def test_spearman_energy_metric_handles_order_and_ties() -> None:
    assert spearman_rank_correlation([(1.0, 0.1), (2.0, 0.2), (3.0, 0.9)]) == pytest.approx(1.0)
    assert spearman_rank_correlation([(1.0, 0.9), (2.0, 0.2), (3.0, 0.1)]) == pytest.approx(-1.0)
    assert spearman_rank_correlation([(1.0, 0.5)]) is None
    assert spearman_rank_correlation([(1.0, 0.5), (2.0, 0.5)]) is None


def test_runner_retains_controlled_provider_failure_as_result_row(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "track.wav").write_bytes(b"audio")
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, _manifest_payload())
    manifest = load_dataset_manifest(manifest_path.resolve(), dataset_root=dataset.resolve())

    class FailingService:
        def analyze_path(self, path: str, *, preferred_provider: str | None = None):
            raise ProviderRuntimeFailure("decode failed", provider="fake")

    ticks = iter((10.0, 10.125))
    report = MIRBenchmarkRunner(
        analysis_service=FailingService(),
        timer=lambda: next(ticks),
    ).run(
        manifest,
        preferred_provider="fake",
        source_commit="abc123",
        generated_at="2026-07-17T00:00:00+00:00",
    )

    assert report.rows[0].status == "controlled_failure"
    assert report.rows[0].error_code == "provider_runtime_error"
    assert report.rows[0].runtime_ms == 125.0
    assert report.summary["controlled_failures"] == 1
    assert report.summary["uncontrolled_failures"] == 0
    assert report.acceptance_gates["no_uncontrolled_failures"] is True


def test_runner_aggregates_metrics_and_serializes_deterministically(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    for name in ("one.wav", "two.wav", "three.wav"):
        (dataset / name).write_bytes(b"audio")
    payload = _manifest_payload(item_path="one.wav")
    payload["items"] = [
        {
            "id": "one",
            "path": "one.wav",
            "reference": {"bpm": 120.0, "key": {"camelot": "8B"}, "energy_rank": 1},
        },
        {
            "id": "two",
            "path": "two.wav",
            "reference": {"bpm": 128.0, "key": {"camelot": "9B"}, "energy_rank": 2},
        },
        {
            "id": "three",
            "path": "three.wav",
            "reference": {"bpm": 130.0, "key": {"camelot": "10B"}, "energy_rank": 3},
        },
    ]
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, payload)
    manifest = load_dataset_manifest(manifest_path.resolve(), dataset_root=dataset.resolve())

    results = {
        "one.wav": _canonical_result(str(dataset / "one.wav"), bpm=120.0, camelot="8B", key="8B", energy=0.1),
        "two.wav": _canonical_result(str(dataset / "two.wav"), bpm=64.0, camelot="9A", key="9A", energy=0.4),
        "three.wav": _canonical_result(str(dataset / "three.wav"), bpm=145.0, camelot="11B", key="11B", energy=0.9),
    }

    class FakeService:
        def analyze_path(self, path: str, *, preferred_provider: str | None = None):
            return results[Path(path).name]

    ticks = iter((0.0, 0.010, 1.0, 1.020, 2.0, 2.030))
    report = MIRBenchmarkRunner(
        analysis_service=FakeService(),
        timer=lambda: next(ticks),
    ).run(
        manifest,
        preferred_provider="fake",
        source_commit="abc123",
        generated_at="2026-07-17T00:00:00+00:00",
    )

    assert [row.bpm_classification for row in report.rows] == ["exact", "half_double", "miss"]
    assert [row.key_classification for row in report.rows] == ["exact", "relative", "adjacent"]
    assert report.summary["energy"]["spearman_rank_correlation"] == pytest.approx(1.0)
    assert report.summary["runtime_ms"]["median"] == 20.0
    assert report.summary["runtime_ms"]["p95"] == pytest.approx(29.0)
    assert report.to_json() == report.to_json()
    parsed = json.loads(report.to_json())
    assert parsed["decision_status"] == "manual_review_required"


def test_real_librosa_provider_runs_through_benchmark_harness(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    track = dataset / "track.wav"
    _write_click_chord(track)
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, _manifest_payload())
    manifest = load_dataset_manifest(manifest_path.resolve(), dataset_root=dataset.resolve())

    report = MIRBenchmarkRunner().run(
        manifest,
        preferred_provider="librosa",
        source_commit="synthetic-test",
        generated_at="2026-07-17T00:00:00+00:00",
    )

    assert len(report.rows) == 1
    assert report.rows[0].status == "success"
    assert report.rows[0].provider == "librosa"
    assert report.rows[0].algorithm_version == "baseline-librosa-mir-v1"
    assert report.summary["attempted"] == 1
    assert report.summary["succeeded"] == 1
    assert report.decision_status == "manual_review_required"

    output = tmp_path / "reports" / "benchmark.json"
    written = write_benchmark_report(report, output.resolve())
    assert written == output.resolve()
    persisted = json.loads(written.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == "applaylist-mir-benchmark-report-v1"
    assert persisted["manifest"]["dataset_name"] == "synthetic-test"
