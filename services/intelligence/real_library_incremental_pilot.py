from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from core.analysis.provider_contract import CanonicalAnalysisResult
from core.analysis.provider_service import RoutedAnalysisService
from core.intelligence.music_dna import build_music_dna
from data.models.analysis_evidence_record import AnalysisEvidenceRecord
from data.models.track_record import TrackRecord
from data.repositories.analysis_evidence_repository import AnalysisEvidenceRepository
from data.repositories.track_repository import TrackRepository
from services.analysis.batch_runner import AnalysisBatchRunner
from services.analysis.job_service import AnalysisJobService
from services.analysis.result_store import AnalysisResultStore
from services.library.identity import ContentTrackIdentityService
from services.intelligence.real_library_pilot import (
    MaterializedTrackEvidence,
    RealLibraryPilotError,
    _analysis_revision,
    _case_specs,
    _load_json,
    _prepare_database,
    _track_inputs,
    _validate_snapshot,
    materialize_cases,
    private_runtime_manifest,
    required_track_ids,
    reviewer_packet,
)

REAL_LIBRARY_INCREMENTAL_RECONCILIATION_VERSION = (
    "real-library-incremental-evidence-reconciliation-r1"
)
ProgressCallback = Callable[[Mapping[str, int | str]], None]


@dataclass(frozen=True, slots=True)
class ReconciliationStats:
    targets_total: int
    evidence_reused: int
    provider_executed: int
    succeeded: int
    failed: int
    remaining: int

    def as_progress(self, *, stage: str) -> dict[str, int | str]:
        return {
            "stage": stage,
            "targets_total": self.targets_total,
            "evidence_reused": self.evidence_reused,
            "provider_executed": self.provider_executed,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "remaining": self.remaining,
        }


class _CountingAnalysisService:
    def __init__(self, delegate: RoutedAnalysisService) -> None:
        self._delegate = delegate
        self.provider_calls = 0

    def execution_identity(self, *, preferred_provider: str | None = None):
        return self._delegate.execution_identity(preferred_provider=preferred_provider)

    def analyze_path(self, path: str, *, preferred_provider: str | None = None):
        self.provider_calls += 1
        return self._delegate.analyze_path(path, preferred_provider=preferred_provider)


def _canonical_from_evidence(
    *,
    record: AnalysisEvidenceRecord,
    path: str,
) -> CanonicalAnalysisResult:
    if record.status != "succeeded":
        raise RealLibraryPilotError("reconciled analysis evidence must be successful")
    return CanonicalAnalysisResult(
        path=path,
        provider=record.provider,
        bpm=record.bpm,
        bpm_confidence=record.bpm_confidence,
        key=record.camelot or record.key_tonic,
        key_confidence=record.key_confidence,
        energy=record.energy,
        loudness_db=record.loudness_db,
        duration_seconds=record.duration_seconds,
        genre_hint=record.genre_hint,
        analysis_status="ok",
        analysis_version=record.analysis_version,
        key_tonic=record.key_tonic,
        key_scale=record.key_scale,
        camelot=record.camelot,
        beat_stability=record.beat_stability,
        harmonic_ratio=record.harmonic_ratio,
        percussive_ratio=record.percussive_ratio,
        provider_version=record.provider_version,
        algorithm_version=record.algorithm_version,
        warnings=record.warnings,
    )


def _emit(progress: ProgressCallback | None, stats: ReconciliationStats, *, stage: str) -> None:
    if progress is not None:
        progress(stats.as_progress(stage=stage))


def reconcile_real_tracks(
    *,
    snapshot_raw: Mapping[str, Any],
    selection_raw: Mapping[str, Any],
    analysis_database_path: str | Path,
    analysis_service: RoutedAnalysisService | None = None,
    identity_service: ContentTrackIdentityService | None = None,
    progress: ProgressCallback | None = None,
) -> tuple[dict[str, MaterializedTrackEvidence], ReconciliationStats]:
    """Resolve real audio into canonical reusable analysis evidence.

    Actual file bytes remain the content authority. The historical inventory file
    signature is retained as provenance only. Expensive MIR runs only when Bundle 55
    cannot reuse exact successful analysis evidence for the canonical content ID.
    """
    _validate_snapshot(snapshot_raw)
    tracks = _track_inputs(snapshot_raw)
    selected_ids = required_track_ids(selection_raw)
    missing = tuple(track_id for track_id in selected_ids if track_id not in tracks)
    if missing:
        raise RealLibraryPilotError(f"curated selection references unknown tracks: {missing}")

    _prepare_database(analysis_database_path)
    identity = identity_service or ContentTrackIdentityService()
    routed = analysis_service or RoutedAnalysisService()
    counted = _CountingAnalysisService(routed)
    track_repository = TrackRepository()
    evidence_repository = AnalysisEvidenceRepository()
    result_store = AnalysisResultStore(evidence_repository)
    jobs = AnalysisJobService()

    stats = ReconciliationStats(
        targets_total=len(selected_ids),
        evidence_reused=0,
        provider_executed=0,
        succeeded=0,
        failed=0,
        remaining=len(selected_ids),
    )
    _emit(progress, stats, stage="analysis_reconciliation_started")

    materialized: dict[str, MaterializedTrackEvidence] = {}
    for snapshot_track_id in selected_ids:
        source = tracks[snapshot_track_id]
        try:
            content_identity = identity.identify(source.absolute_path)
        except Exception as exc:
            raise RealLibraryPilotError(
                f"content identity failed for selected track {snapshot_track_id}"
            ) from exc

        canonical_track_id = content_identity.track_id
        track_repository.upsert(
            TrackRecord(
                track_id=canonical_track_id,
                path=source.absolute_path,
                title=source.display_name,
                artist=source.artist,
                genre=source.genre,
            )
        )

        before_calls = counted.provider_calls
        job = jobs.create_job(
            track_ids=[canonical_track_id],
            preferred_provider="librosa",
        )
        terminal = AnalysisBatchRunner(
            analysis_service=counted,  # type: ignore[arg-type]
            job_service=jobs,
            result_store=result_store,
            track_repository=track_repository,
        ).run(job.job_id)
        provider_ran = counted.provider_calls > before_calls

        record = evidence_repository.latest_success_for_track(canonical_track_id)
        failed = terminal.status != "done" or terminal.counts.failed != 0 or record is None
        if failed:
            stats = ReconciliationStats(
                targets_total=stats.targets_total,
                evidence_reused=stats.evidence_reused,
                provider_executed=stats.provider_executed + int(provider_ran),
                succeeded=stats.succeeded,
                failed=stats.failed + 1,
                remaining=max(0, stats.remaining - 1),
            )
            _emit(progress, stats, stage="analysis_target_failed")
            raise RealLibraryPilotError(
                f"canonical analysis evidence unavailable for selected track {snapshot_track_id}"
            )

        canonical = _canonical_from_evidence(record=record, path=source.absolute_path)
        if canonical.duration_seconds is None or canonical.duration_seconds <= 0.0:
            raise RealLibraryPilotError(
                f"positive duration evidence missing for selected track {snapshot_track_id}"
            )
        revision = _analysis_revision(source, canonical, content_identity.digest_hex)
        content_ref = f"sha256:{content_identity.digest_hex}"
        dna = build_music_dna(
            track_id=snapshot_track_id,
            content_identity=content_ref,
            analysis_revision=revision,
            evidence_id=record.evidence_id,
            input_identity=content_ref,
            canonical=canonical,
            rhythmic_structure=None,
            benchmark_status="real-library-pilot-r1-candidate",
        )
        materialized[snapshot_track_id] = MaterializedTrackEvidence(
            source=source,
            content_sha256=content_identity.digest_hex,
            canonical=canonical,
            music_dna=dna,
        )

        stats = ReconciliationStats(
            targets_total=stats.targets_total,
            evidence_reused=stats.evidence_reused + int(not provider_ran),
            provider_executed=stats.provider_executed + int(provider_ran),
            succeeded=stats.succeeded + 1,
            failed=stats.failed,
            remaining=max(0, stats.remaining - 1),
        )
        _emit(
            progress,
            stats,
            stage="analysis_provider_executed" if provider_ran else "analysis_evidence_reused",
        )

    _emit(progress, stats, stage="analysis_reconciliation_complete")
    return materialized, stats


def default_analysis_database_path(output_dir: str | Path) -> Path:
    output = Path(output_dir).expanduser().resolve()
    return output.parent / "APPLAYLIST_REAL_LIBRARY_ANALYSIS_EVIDENCE_R1.sqlite3"


def materialize_real_library_pilot_incremental_r1(
    *,
    snapshot_path: str | Path,
    selection_path: str | Path,
    output_dir: str | Path,
    database_path: str | Path,
    analysis_database_path: str | Path | None,
    generated_at: str,
    blinding_seed: str,
    analysis_service: RoutedAnalysisService | None = None,
    identity_service: ContentTrackIdentityService | None = None,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    snapshot_raw = _load_json(snapshot_path)
    selection_raw = _load_json(selection_path)
    persistent_analysis_db = (
        Path(analysis_database_path)
        if analysis_database_path is not None
        else default_analysis_database_path(output_dir)
    )
    evidence, stats = reconcile_real_tracks(
        snapshot_raw=snapshot_raw,
        selection_raw=selection_raw,
        analysis_database_path=persistent_analysis_db,
        analysis_service=analysis_service,
        identity_service=identity_service,
        progress=progress,
    )
    cases = materialize_cases(
        snapshot_raw=snapshot_raw,
        selection_raw=selection_raw,
        evidence=evidence,
        database_path=database_path,
        generated_at=generated_at,
        blinding_seed=blinding_seed,
    )
    if len(cases) != len(_case_specs(selection_raw)):
        raise RealLibraryPilotError("not every curated case produced a blind plan pair")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    private_path = output / "APPLAYLIST_REAL_LIBRARY_RUNTIME_EVIDENCE_R1.private.json"
    reviewer_path = output / "APPLAYLIST_BLINDED_HUMAN_DJ_REVIEW_PACKET_R1.json"
    private_payload = private_runtime_manifest(
        snapshot_raw=snapshot_raw,
        evidence=evidence,
        cases=cases,
        generated_at=generated_at,
    )
    private_payload["analysis_reconciliation"] = {
        "version": REAL_LIBRARY_INCREMENTAL_RECONCILIATION_VERSION,
        "targets_total": stats.targets_total,
        "evidence_reused": stats.evidence_reused,
        "provider_executed": stats.provider_executed,
        "succeeded": stats.succeeded,
        "failed": stats.failed,
        "analysis_database": "persistent-private-analysis-evidence",
    }
    for row in private_payload.get("tracks", []):
        track_id = str(row.get("track_id", ""))
        if track_id in evidence:
            row["analysis_evidence_id"] = evidence[track_id].music_dna.identity.evidence_refs[0]

    reviewer_payload = reviewer_packet(
        snapshot_raw=snapshot_raw,
        evidence=evidence,
        cases=cases,
        generated_at=generated_at,
    )
    private_path.write_text(
        json.dumps(private_payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    reviewer_path.write_text(
        json.dumps(reviewer_payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    return {
        "private_runtime_manifest": str(private_path),
        "blind_reviewer_packet": str(reviewer_path),
        "private_runtime_manifest_sha256": hashlib.sha256(private_path.read_bytes()).hexdigest(),
        "blind_reviewer_packet_sha256": hashlib.sha256(reviewer_path.read_bytes()).hexdigest(),
        "analysis_reconciliation": asdict(stats),
        "analysis_database_path": str(persistent_analysis_db),
    }


__all__ = [
    "REAL_LIBRARY_INCREMENTAL_RECONCILIATION_VERSION",
    "ReconciliationStats",
    "default_analysis_database_path",
    "materialize_real_library_pilot_incremental_r1",
    "reconcile_real_tracks",
]
