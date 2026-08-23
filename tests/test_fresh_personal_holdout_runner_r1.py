from __future__ import annotations

import hashlib

import pytest

from core.intelligence.curated_real_library_review_contract import CuratedSetRole
from services.intelligence.fresh_personal_holdout_runner import (
    FreshPersonalHoldoutRunnerError,
    _case_spec_pool,
    _write_review_csv,
)


def _snapshot(track_count: int = 40) -> dict:
    tracks = []
    for index in range(track_count):
        signature = hashlib.sha256(f"track-{index}".encode()).hexdigest()
        tracks.append(
            {
                "track_id": f"trk_{signature[:24]}",
                "absolute_path": f"/private/library/{index}.mp3",
                "file_signature": signature,
                "display_name": f"Artist {index} - Track {index}",
                "artist": f"Artist {index}",
                "genre": "Techno",
                "energy": 7.0,
            }
        )
    return {
        "schema": "applaylist-local-library-snapshot-r1",
        "snapshot_id": "snapshot-fresh",
        "snapshot_version": "local-library-subset-r1",
        "library_fingerprint": "snapshot:fresh:fingerprint",
        "created_date": "2026-08-23",
        "scope": {"kind": "REAL_INVENTORY_BACKED_SUBSET"},
        "privacy": {"publishable_to_public_repo": False},
        "tracks": tracks,
    }


def test_case_pool_is_deterministic_balanced_and_has_no_model_inputs() -> None:
    first = _case_spec_pool(_snapshot(), sampling_seed="seed-1", cases_per_role=8, candidate_scope_size=16)
    replay = _case_spec_pool(_snapshot(), sampling_seed="seed-1", cases_per_role=8, candidate_scope_size=16)
    assert first == replay
    assert len(first["case_specs"]) == 8 * len(tuple(CuratedSetRole))
    for role in CuratedSetRole:
        assert sum(row["set_role"] == role.value for row in first["case_specs"]) == 8
    text = str(first).lower()
    assert "challenger" not in text
    assert "preference" not in text
    assert "rating" not in text


def test_case_pool_changes_with_seed() -> None:
    left = _case_spec_pool(_snapshot(), sampling_seed="seed-a")
    right = _case_spec_pool(_snapshot(), sampling_seed="seed-b")
    assert left != right


def test_case_pool_requires_bounded_minimum_library() -> None:
    with pytest.raises(FreshPersonalHoldoutRunnerError, match="at least 17 tracks"):
        _case_spec_pool(_snapshot(16), sampling_seed="seed")


def test_review_csv_contains_only_curation_fields_and_empty_human_labels(tmp_path) -> None:
    path = tmp_path / "review.csv"
    rows = [
        {
            "case_id": "case-1",
            "set_role": "opening",
            "assignment_id": "assignment-1",
        }
    ]
    _write_review_csv(path, rows)
    text = path.read_text(encoding="utf-8")
    assert "transition_smoothness" not in text
    assert "phrase_alignment" not in text
    assert "energy_flow_plan_a" in text
    assert "dramaturgical_fit_plan_b" in text
    assert "set_coherence_plan_a" in text
    assert "alternative_usefulness_plan_b" in text
    assert "plan_a,plan_b" not in text
    assert "case-1,opening,assignment-1" in text


def test_snapshot_case_pool_never_exposes_absolute_paths() -> None:
    pool = _case_spec_pool(_snapshot(), sampling_seed="seed")
    assert "/private/library/" not in str(pool)
