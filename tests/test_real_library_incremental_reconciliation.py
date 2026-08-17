from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.analysis.execution_identity import AnalysisExecutionIdentity
from core.analysis.provider_contract import CanonicalAnalysisResult
from core.config.settings import get_settings
from core.library.track_metadata import TrackIdentity
from services.intelligence.real_library_incremental_pilot import (
    default_analysis_database_path,
    reconcile_real_tracks,
)
from services.intelligence.real_library_pilot import RealLibraryPilotError


@pytest.fixture(autouse=True)
def restore_database_environment():
    previous = os.environ.get("DATABASE_URL")
    yield
    if previous is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous
    get_settings.cache_clear()


def _snapshot(path: str = "/library/a.wav") -> dict[str, object]:
    return {
        "schema": "applaylist-local-library-snapshot-r1",
        "snapshot_id": "snapshot-r1",
        "snapshot_version": "r1",
        "library_fingerprint": "library-fingerprint-r1",
        "created_date": "2026-08-17",
        "scope": {"kind": "REAL_INVENTORY_BACKED_SUBSET"},
        "privacy": {"publishable_to_public_repo": False},
        "tracks": [
            {
                "track_id": "snapshot-track-a",
                "absolute_path": path,
                "file_signature": "opaque-inventory-signature",
                "display_name": "Track A",
                "artist": "Artist A",
                "genre": "Techno",
                "energy": 7,
            }
        ],
    }


def _selection() -> dict[str, object]:
    return {
        "schema": "applaylist-curated-case-selection-r1",
        "case_specs": [
            {
                "case_spec_id": "case-a",
                "seed_track_id": "snapshot-track-a",
                "candidate_scope_track_ids": ["snapshot-track-a"],
            }
        ],
    }


def _result(path: str, *, provider_version: str = "0.10.2.post1") -> CanonicalAnalysisResult:
    return CanonicalAnalysisResult(
        path=path,
        provider="librosa",
        bpm=140.0,
        bpm_confidence=0.9,
        key="11A",
        key_confidence=0.88,
        energy=0.72,
        loudness_db=-10.0,
        duration_seconds=300.0,
        genre_hint=None,
        key_tonic="F#",
        key_scale="minor",
        camelot="11A",
        beat_stability=0.85,
        harmonic_ratio=0.55,
        percussive_ratio=0.45,
        provider_version=provider_version,
        algorithm_version="baseline-librosa-mir-v1",
    )


class StaticIdentityService:
    def __init__(self, digest: str = "a" * 64) -> None:
        self.digest = digest

    def identify(self, path: str | Path) -> TrackIdentity:
        return TrackIdentity(
            track_id=f"aptrack:v1:sha256:{self.digest}",
            digest_algorithm="sha256",
            digest_hex=self.digest,
            source_path=str(path),
            size_bytes=123,
            mtime_ns=1,
        )


class FakeAnalysisService:
    def __init__(self, *, provider_version: str = "0.10.2.post1", fail: bool = False) -> None:
        self.provider_version = provider_version
        self.fail = fail
        self.calls: list[str] = []

    def execution_identity(self, *, preferred_provider: str | None = None):
        return AnalysisExecutionIdentity(
            provider="librosa",
            analysis_version="canonical-mir-v1",
            provider_version=self.provider_version,
            algorithm_version="baseline-librosa-mir-v1",
        )

    def analyze_path(self, path: str, *, preferred_provider: str | None = None):
        self.calls.append(path)
        if self.fail:
            raise RuntimeError("simulated provider failure")
        return _result(path, provider_version=self.provider_version)


def test_cold_then_warm_real_library_run_eliminates_provider_execution(tmp_path: Path) -> None:
    database = tmp_path / "persistent-analysis.sqlite3"
    service = FakeAnalysisService()
    identity = StaticIdentityService()

    first, cold = reconcile_real_tracks(
        snapshot_raw=_snapshot(),
        selection_raw=_selection(),
        analysis_database_path=database,
        analysis_service=service,  # type: ignore[arg-type]
        identity_service=identity,  # type: ignore[arg-type]
    )
    second, warm = reconcile_real_tracks(
        snapshot_raw=_snapshot(),
        selection_raw=_selection(),
        analysis_database_path=database,
        analysis_service=service,  # type: ignore[arg-type]
        identity_service=identity,  # type: ignore[arg-type]
    )

    assert service.calls == ["/library/a.wav"]
    assert cold.provider_executed == 1
    assert cold.evidence_reused == 0
    assert warm.provider_executed == 0
    assert warm.evidence_reused == 1
    assert first["snapshot-track-a"].content_sha256 == "a" * 64
    assert second["snapshot-track-a"].music_dna.identity.evidence_refs == (
        first["snapshot-track-a"].music_dna.identity.evidence_refs[0],
    )


def test_changed_content_identity_executes_only_invalidated_track(tmp_path: Path) -> None:
    database = tmp_path / "persistent-analysis.sqlite3"
    service = FakeAnalysisService()
    identity = StaticIdentityService("a" * 64)

    reconcile_real_tracks(
        snapshot_raw=_snapshot(),
        selection_raw=_selection(),
        analysis_database_path=database,
        analysis_service=service,  # type: ignore[arg-type]
        identity_service=identity,  # type: ignore[arg-type]
    )
    identity.digest = "b" * 64
    _, changed = reconcile_real_tracks(
        snapshot_raw=_snapshot(),
        selection_raw=_selection(),
        analysis_database_path=database,
        analysis_service=service,  # type: ignore[arg-type]
        identity_service=identity,  # type: ignore[arg-type]
    )

    assert service.calls == ["/library/a.wav", "/library/a.wav"]
    assert changed.provider_executed == 1
    assert changed.evidence_reused == 0


def test_provider_drift_failure_never_falls_back_to_stale_success(tmp_path: Path) -> None:
    database = tmp_path / "persistent-analysis.sqlite3"
    identity = StaticIdentityService()

    reconcile_real_tracks(
        snapshot_raw=_snapshot(),
        selection_raw=_selection(),
        analysis_database_path=database,
        analysis_service=FakeAnalysisService(provider_version="0.10.2.post1"),  # type: ignore[arg-type]
        identity_service=identity,  # type: ignore[arg-type]
    )

    with pytest.raises(RealLibraryPilotError, match="canonical analysis evidence unavailable"):
        reconcile_real_tracks(
            snapshot_raw=_snapshot(),
            selection_raw=_selection(),
            analysis_database_path=database,
            analysis_service=FakeAnalysisService(provider_version="0.10.3", fail=True),  # type: ignore[arg-type]
            identity_service=identity,  # type: ignore[arg-type]
        )


def test_progress_is_bounded_and_does_not_expose_local_paths(tmp_path: Path) -> None:
    events: list[dict[str, int | str]] = []
    reconcile_real_tracks(
        snapshot_raw=_snapshot(),
        selection_raw=_selection(),
        analysis_database_path=tmp_path / "persistent-analysis.sqlite3",
        analysis_service=FakeAnalysisService(),  # type: ignore[arg-type]
        identity_service=StaticIdentityService(),  # type: ignore[arg-type]
        progress=lambda event: events.append(dict(event)),
    )

    assert events
    assert events[-1]["stage"] == "analysis_reconciliation_complete"
    assert events[-1]["targets_total"] == 1
    assert events[-1]["remaining"] == 0
    assert all("/library/" not in str(value) for event in events for value in event.values())


def test_default_analysis_database_is_stable_across_run_directories(tmp_path: Path) -> None:
    root = tmp_path / "real-library-pilot-r1"
    first = default_analysis_database_path(root / "run-a")
    second = default_analysis_database_path(root / "run-b")

    assert first == second
    assert first.name == "APPLAYLIST_REAL_LIBRARY_ANALYSIS_EVIDENCE_R1.sqlite3"
