from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from services.intelligence.fresh_holdout_reviewer_workspace import (
    finalize_fresh_holdout_reviewer_workspace,
)
from services.intelligence.fresh_personal_holdout_runner import FreshPersonalHoldoutRunnerError


def _cases() -> list[dict]:
    return [
        {
            "case_id": f"case-{index}",
            "set_role": ("opening", "build", "mid_set", "peak", "reset", "closing")[
                (index - 1) // 4
            ],
            "assignment_id": f"assignment-{index}",
            "plan_a": [f"A{index}-1", f"A{index}-2"],
            "plan_b": [f"B{index}-1", f"B{index}-2"],
        }
        for index in range(1, 25)
    ]


def _prior_packet(tmp_path: Path, *, duplicate_current_plan: bool = False) -> Path:
    path = tmp_path / "prior-reviewer.json"
    plan_a = ["historical-a1", "historical-a2"]
    plan_b = ["historical-b1", "historical-b2"]
    if duplicate_current_plan:
        plan_a = ["A1-1", "A1-2"]
    path.write_text(
        json.dumps(
            {
                "schema": "applaylist-blind-human-dj-review-packet-r1",
                "cases": [
                    {
                        "case_id": "historical-case",
                        "set_role": "opening",
                        "assignment_id": "historical-assignment",
                        "plan_a": plan_a,
                        "plan_b": plan_b,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _files(tmp_path: Path) -> dict[str, str]:
    private_path = tmp_path / "private.json"
    reviewer_path = tmp_path / "reviewer.json"
    csv_path = tmp_path / "review.csv"
    cases = _cases()
    private_path.write_text(
        json.dumps(
            {
                "schema": "applaylist-fresh-personal-holdout-private-r1",
                "canonical_sha": "canonical-sha",
                "preregistration_fingerprint": "prereg:fingerprint",
                "sampling_policy": {"fallback_count": 12},
                "selection": {
                    "manifest_fingerprint": "selection:fingerprint",
                    "selected_case_ids": [case["case_id"] for case in cases],
                    "fallback_case_ids": [f"fallback-{index}" for index in range(12)],
                },
                "effective_cohort": {"cohort_id": "cohort:id"},
                "challenger_frozen_before_reviewer_publication": True,
                "challenger_evidence": [{"case_id": "private-only"}],
            }
        ),
        encoding="utf-8",
    )
    reviewer_path.write_text(
        json.dumps(
            {
                "schema": "applaylist-fresh-personal-holdout-reviewer-r1",
                "packet_fingerprint": "prebind",
                "cases": cases,
            }
        ),
        encoding="utf-8",
    )
    csv_path.write_text("old\n", encoding="utf-8")
    return {
        "private_manifest": str(private_path),
        "reviewer_packet": str(reviewer_path),
        "review_csv": str(csv_path),
    }


def _finalize(tmp_path: Path) -> dict[str, str]:
    return finalize_fresh_holdout_reviewer_workspace(
        _files(tmp_path),
        prior_reviewer_packet_paths=(_prior_packet(tmp_path),),
    )


def test_finalize_binds_workspace_without_exposing_challenger(tmp_path: Path) -> None:
    result = _finalize(tmp_path)
    reviewer = Path(result["reviewer_packet"]).read_text(encoding="utf-8")
    assert "prereg:fingerprint" in reviewer
    assert "selection:fingerprint" in reviewer
    assert "cohort:id" in reviewer
    assert "prior-exposure-registry:" in reviewer
    assert "challenger_evidence" not in reviewer
    assert "left_score" not in reviewer
    assert result["curation_session_id"].startswith("curation-session:")


def test_finalize_leaves_all_human_and_attestation_fields_empty(tmp_path: Path) -> None:
    result = _finalize(tmp_path)
    rows = list(csv.DictReader(Path(result["review_csv"]).open("r", encoding="utf-8")))
    assert len(rows) == 24
    human_fields = (
        "reviewer_ref",
        "preference",
        "energy_flow_plan_a",
        "energy_flow_plan_b",
        "dramaturgical_fit_plan_a",
        "dramaturgical_fit_plan_b",
        "set_coherence_plan_a",
        "set_coherence_plan_b",
        "alternative_usefulness_plan_a",
        "alternative_usefulness_plan_b",
        "confidence",
        "prior_case_exposure",
        "judgment_mode",
        "transition_execution_used",
        "transition_preview_heard",
        "algorithm_identity_was_hidden",
        "reason_codes",
        "notes",
        "observed_at",
    )
    for row in rows:
        assert row["dataset_role"] == "personal_holdout"
        assert row["curation_session_id"].startswith("curation-session:")
        assert all(row[field] == "" for field in human_fields)


def test_private_manifest_binds_final_reviewer_packet(tmp_path: Path) -> None:
    result = _finalize(tmp_path)
    private = json.loads(Path(result["private_manifest"]).read_text(encoding="utf-8"))
    binding = private["reviewer_workspace_binding"]
    assert binding["reviewer_packet_fingerprint"] == result["reviewer_packet_fingerprint"]
    assert binding["prior_exposure_registry_fingerprint"] == result[
        "prior_exposure_registry_fingerprint"
    ]
    assert binding["human_labels_present_at_freeze"] is False


def test_finalize_requires_prior_exposure_source(tmp_path: Path) -> None:
    with pytest.raises(FreshPersonalHoldoutRunnerError, match="prior reviewer packet"):
        finalize_fresh_holdout_reviewer_workspace(
            _files(tmp_path),
            prior_reviewer_packet_paths=(),
        )


def test_finalize_rejects_any_previously_exposed_plan(tmp_path: Path) -> None:
    with pytest.raises(FreshPersonalHoldoutRunnerError, match="plan sequence already exposed"):
        finalize_fresh_holdout_reviewer_workspace(
            _files(tmp_path),
            prior_reviewer_packet_paths=(
                _prior_packet(tmp_path, duplicate_current_plan=True),
            ),
        )
