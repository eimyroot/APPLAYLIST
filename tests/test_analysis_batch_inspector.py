from __future__ import annotations

from pathlib import Path

import pytest

from core.analysis.provider_contract import CanonicalAnalysisResult, ProviderRuntimeFailure
from core.config.settings import get_settings
from data.models.track_record import TrackRecord
from data.repositories.analysis_evidence_repository import AnalysisEvidenceRepository
from data.repositories.track_repository import TrackRepository
from services.analysis.batch_runner import AnalysisBatchRunner
from services.analysis.inspector import AnalysisInspectorService
from services.analysis.job_service import AnalysisJobService
from services.analysis.result_store import AnalysisResultStore


@pytest.fixture
def isolated_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    database_path = tmp_path / "bundle50-batch.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    get_settings.cache_clear()
    yield database_path
    get_settings.cache_clear()


def _track(repository: TrackRepository, track_id: str, path: str, *, title: str | None = None) -> None:
    repository.upsert(
        TrackRecord(
            track_id=track_id,
            path=path,
            title=title,
            artist="Test Artist",
            duration_seconds=300.0,
        )
    )


def _result(
    path: str,
    *,
    bpm: float = 140.0,
    bpm_confidence: float = 0.85,
    key_confidence: float = 0.82,
    warnings: tuple[str, ...] = ("baseline provider output is not benchmark-approved",),
) -> CanonicalAnalysisResult:
    return CanonicalAnalysisResult(
        path=path,
        provider="librosa",
        bpm=bpm,
        bpm_confidence=bpm_confidence,
        key="11A",
        key_confidence=key_confidence,
        energy=0.72,
        loudness_db=-10.0,
        duration_seconds=300.0,
        genre_hint=None,
        key_tonic="F#",
        key_scale="minor",
        camelot="11A",
        beat_stability=0.8,
        harmonic_ratio=0.55,
        percussive_ratio=0.45,
        provider_version="0.10.2",
        algorithm_version="baseline-librosa-mir-v1",
        warnings=warnings,
    )


class ScriptedAnalysisService:
    def __init__(self, script: dict[str, CanonicalAnalysisResult | Exception]) -> None:
        self.script = script
        self.calls: list[str] = []

    def analyze_path(
        self,
        path: str,
        *,
        preferred_provider: str | None = None,
    ) -> CanonicalAnalysisResult:
        self.calls.append(path)
        outcome = self.script[path]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class CancellingAnalysisService:
    def __init__(self, job_service: AnalysisJobService, job_id: str) -> None:
        self.job_service = job_service
        self.job_id = job_id
        self.calls: list[str] = []

    def analyze_path(
        self,
        path: str,
        *,
        preferred_provider: str | None = None,
    ) -> CanonicalAnalysisResult:
        self.calls.append(path)
        self.job_service.request_cancel(self.job_id)
        return _result(path)


def test_batch_runner_isolates_track_failures_and_keeps_safe_evidence(
    isolated_database: Path,
) -> None:
    tracks = TrackRepository()
    jobs = AnalysisJobService()
    evidence = AnalysisEvidenceRepository()
    _track(tracks, "track-a", "/private/library/a.wav")
    _track(tracks, "track-b", "/private/library/b.wav")
    _track(tracks, "track-c", "/private/library/c.wav")

    scripted = ScriptedAnalysisService(
        {
            "/private/library/a.wav": _result("/private/library/a.wav"),
            "/private/library/b.wav": ProviderRuntimeFailure(
                "raw provider detail /private/library/b.wav",
                provider="librosa",
            ),
            "/private/library/c.wav": _result(
                "/private/library/c.wav",
                bpm_confidence=0.20,
            ),
        }
    )
    job = jobs.create_job(
        track_ids=["track-a", "track-b", "track-c"],
        preferred_provider="librosa",
    )
    terminal = AnalysisBatchRunner(
        analysis_service=scripted,  # type: ignore[arg-type]
        job_service=jobs,
        result_store=AnalysisResultStore(evidence),
        track_repository=tracks,
    ).run(job.job_id)

    assert terminal.status == "done"
    assert terminal.counts.selected == 3
    assert terminal.counts.completed == 3
    assert terminal.counts.succeeded == 2
    assert terminal.counts.failed == 1
    assert terminal.counts.uncertain == 1
    assert scripted.calls == [
        "/private/library/a.wav",
        "/private/library/b.wav",
        "/private/library/c.wav",
    ]

    failure = evidence.latest_evidence_for_track("track-b")
    assert failure is not None
    assert failure.status == "failed"
    assert failure.error_code == "provider_runtime_error"
    assert failure.error_detail == "Analysis provider failed for this track."
    assert "/private/" not in failure.error_detail


def test_cancel_during_track_finishes_that_evidence_and_stops_next_track(
    isolated_database: Path,
) -> None:
    tracks = TrackRepository()
    jobs = AnalysisJobService()
    evidence = AnalysisEvidenceRepository()
    _track(tracks, "track-a", "/library/a.wav")
    _track(tracks, "track-b", "/library/b.wav")

    job = jobs.create_job(track_ids=["track-a", "track-b"], preferred_provider="librosa")
    cancelling = CancellingAnalysisService(jobs, job.job_id)
    terminal = AnalysisBatchRunner(
        analysis_service=cancelling,  # type: ignore[arg-type]
        job_service=jobs,
        result_store=AnalysisResultStore(evidence),
        track_repository=tracks,
    ).run(job.job_id)

    assert terminal.status == "cancelled"
    assert terminal.cancel_requested is True
    assert terminal.counts.completed == 1
    assert terminal.counts.succeeded == 1
    assert terminal.counts.failed == 0
    assert cancelling.calls == ["/library/a.wav"]
    assert evidence.latest_evidence_for_track("track-a") is not None
    assert evidence.latest_evidence_for_track("track-b") is None


def test_inspector_uses_safe_fields_and_manual_correction_overlay(
    isolated_database: Path,
) -> None:
    tracks = TrackRepository()
    evidence = AnalysisEvidenceRepository()
    inspector = AnalysisInspectorService(
        evidence_repository=evidence,
        track_repository=tracks,
    )
    _track(tracks, "track-a", "/private/secret/fallback.wav", title=None)

    first = AnalysisResultStore(evidence).persist_success(
        track_id="track-a",
        result=_result("/private/secret/fallback.wav"),
    )
    corrected = inspector.apply_correction(
        track_id="track-a",
        values={"bpm": 141.0, "camelot": "12A"},
        reason="confirmed on deck",
    )

    assert corrected.title == "fallback.wav"
    assert corrected.source == "manual-correction"
    assert corrected.corrected is True
    assert corrected.bpm == 141.0
    assert corrected.camelot == "12A"
    assert corrected.effective_evidence_id == first.evidence_id
    assert corrected.correction_id is not None
    assert corrected.uncertain is False
    assert "/private/" not in repr(corrected.to_dict())
    assert "path" not in corrected.to_dict()
    assert inspector.list_items("corrected") == [corrected]


def test_inspector_never_leaks_windows_style_absolute_path(
    isolated_database: Path,
) -> None:
    tracks = TrackRepository()
    evidence = AnalysisEvidenceRepository()
    inspector = AnalysisInspectorService(
        evidence_repository=evidence,
        track_repository=tracks,
    )
    windows_path = r"C:\Users\Eimy\Music\secret\windows-track.wav"
    _track(tracks, "track-windows", windows_path, title=None)
    AnalysisResultStore(evidence).persist_success(
        track_id="track-windows",
        result=_result(windows_path),
    )

    item = inspector.get_item("track-windows")
    assert item is not None
    assert item.title == "windows-track.wav"
    assert "C:\\Users" not in repr(item.to_dict())
    assert "secret" not in item.title
    assert "path" not in item.to_dict()


def test_successful_reanalysis_keeps_correction_history_but_deactivates_old_override(
    isolated_database: Path,
) -> None:
    tracks = TrackRepository()
    evidence = AnalysisEvidenceRepository()
    store = AnalysisResultStore(evidence)
    inspector = AnalysisInspectorService(
        evidence_repository=evidence,
        track_repository=tracks,
    )
    _track(tracks, "track-a", "/library/a.wav", title="A")

    first = store.persist_success(track_id="track-a", result=_result("/library/a.wav", bpm=138.0))
    correction = evidence.append_correction(
        track_id="track-a",
        base_evidence_id=first.evidence_id,
        values={"bpm": 139.0},
        reason="manual verification",
    )
    assert inspector.get_item("track-a").bpm == 139.0  # type: ignore[union-attr]

    second = store.persist_success(track_id="track-a", result=_result("/library/a.wav", bpm=140.0))
    item = inspector.get_item("track-a")
    assert item is not None
    assert item.effective_evidence_id == second.evidence_id
    assert item.bpm == 140.0
    assert item.source == "provider"
    assert item.corrected is False
    assert evidence.latest_correction_for_track("track-a") == correction
    assert evidence.latest_active_correction("track-a", second.evidence_id) is None


def test_failed_reanalysis_preserves_last_good_effective_result_and_failed_filter(
    isolated_database: Path,
) -> None:
    tracks = TrackRepository()
    evidence = AnalysisEvidenceRepository()
    inspector = AnalysisInspectorService(
        evidence_repository=evidence,
        track_repository=tracks,
    )
    _track(tracks, "track-a", "/library/a.wav", title="A")
    store = AnalysisResultStore(evidence)
    store.persist_success(track_id="track-a", result=_result("/library/a.wav", bpm=140.0))
    store.persist_failure(
        track_id="track-a",
        preferred_provider="librosa",
        error=RuntimeError("raw /library/a.wav detail must not escape"),
    )

    item = inspector.get_item("track-a")
    assert item is not None
    assert item.status == "failed"
    assert item.bpm == 140.0
    assert item.error_code == "analysis_internal_error"
    assert item.error_detail == "Analysis failed for this track."
    assert "/library/" not in repr(item.to_dict())
    assert inspector.list_items("failed") == [item]


def test_baseline_warning_alone_does_not_mark_result_uncertain() -> None:
    result = _result("/library/a.wav")
    assert result.warnings
    assert AnalysisResultStore.is_uncertain(result) is False
    assert AnalysisResultStore.is_uncertain(
        _result("/library/a.wav", key_confidence=0.49)
    ) is True
