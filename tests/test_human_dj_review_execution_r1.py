from __future__ import annotations

import sqlite3
from dataclasses import asdict
from pathlib import Path

import pytest

from core.intelligence.curated_real_library_review_contract import (
    REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1,
    CuratedReviewCase,
    CuratedSetRole,
    ReviewPlanStrategy,
    ReviewableSetPlan,
)
from services.intelligence.curated_real_library_review import build_blinded_plan_assignment
from services.intelligence.human_dj_review_execution import (
    BLIND_REVIEW_PACKET_SCHEMA,
    HUMAN_DJ_REVIEW_SUBMISSION_SCHEMA,
    HumanDJReviewExecutionError,
    HumanDJReviewLedger,
    aggregate_human_dj_review,
    build_reviewer_workspace,
    ingest_review_submission,
    reviewer_packet_fingerprint,
    validate_reviewer_packet,
)


def _plan(index: int, strategy: ReviewPlanStrategy) -> ReviewableSetPlan:
    name = "baseline-a" if strategy is ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT else "candidate-b"
    tracks = tuple(f"track-{(index * 3 + offset) % 40:02d}" for offset in range(3))
    return ReviewableSetPlan(
        plan_id=f"plan:{name}:{index:02d}",
        strategy=strategy,
        result_id=f"result:{name}:{index:02d}",
        path_id=f"path:{name}:{index:02d}",
        ordered_track_ids=tracks,
        transition_ids=(f"transition:{name}:{index:02d}",),
        evidence_refs=(f"evidence:{name}:{index:02d}",),
    )


def _case(index: int, role: CuratedSetRole) -> CuratedReviewCase:
    return CuratedReviewCase(
        case_id=f"case-{index:02d}",
        snapshot_ref=("snapshot-r1", "1"),
        scenario_fingerprint=f"scenario:{index:02d}",
        set_role=role,
        benchmark_ref=("real-library-greedy-vs-beam", "curated-real-library-benchmark-r1"),
        greedy_plan=_plan(index, ReviewPlanStrategy.GREEDY_RECOMMEND_NEXT),
        beam_plan=_plan(index, ReviewPlanStrategy.BOUNDED_BEAM),
        engineering_acceptance_passed=True,
        evidence_refs=(f"evidence:case:{index:02d}",),
    )


def _cases() -> tuple[CuratedReviewCase, ...]:
    roles = tuple(CuratedSetRole)
    return tuple(_case(index, roles[index % len(roles)]) for index in range(12))


def _packet_and_private() -> tuple[dict[str, object], dict[str, object]]:
    cases = _cases()
    assignments = tuple(
        build_blinded_plan_assignment(case=case, blinding_seed="bundle-63-test-seed")
        for case in cases
    )
    packet_cases: list[dict[str, object]] = []
    for case, assignment in zip(cases, assignments, strict=True):
        plans = {
            case.greedy_plan.plan_id: case.greedy_plan,
            case.beam_plan.plan_id: case.beam_plan,
        }
        plan_a = plans[assignment.slot_a_plan_id]
        plan_b = plans[assignment.slot_b_plan_id]
        packet_cases.append(
            {
                "case_id": case.case_id,
                "set_role": case.set_role.value,
                "assignment_id": assignment.assignment_id,
                "plan_a": [f"Display {track_id}" for track_id in plan_a.ordered_track_ids],
                "plan_b": [f"Display {track_id}" for track_id in plan_b.ordered_track_ids],
                "required_review_dimensions": [
                    dimension.value for dimension in REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1
                ],
                "allowed_preference": ["plan_a", "plan_b", "tie", "abstain"],
            }
        )
    packet: dict[str, object] = {
        "schema": BLIND_REVIEW_PACKET_SCHEMA,
        "protocol_version": "human-dj-review-r1",
        "generated_at": "2026-08-19T22:00:00+02:00",
        "snapshot_ref": ["snapshot-r1", "1"],
        "algorithm_identity_hidden": True,
        "cases": packet_cases,
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
    }
    packet["packet_fingerprint"] = reviewer_packet_fingerprint(packet)

    private = {
        "schema": "applaylist-private-runtime-music-evidence-r1",
        "materializer_version": "real-library-evidence-materializer-r1",
        "generated_at": "2026-08-19T22:00:00+02:00",
        "snapshot_ref": ["snapshot-r1", "1"],
        "library_fingerprint": "sha256:fixture-library",
        "privacy": {
            "contains_local_absolute_paths": True,
            "publishable_to_public_repo": False,
            "storage_class": "CASER_PRIVATE_EVIDENCE",
        },
        "tracks": [{"track_id": f"track-{index:02d}"} for index in range(40)],
        "cases": [
            {
                "case": asdict(case),
                "assignment": asdict(assignment),
                "greedy_status": "complete",
                "beam_status": "complete",
                "greedy_result_id": case.greedy_plan.result_id,
                "beam_result_id": case.beam_plan.result_id,
            }
            for case, assignment in zip(cases, assignments, strict=True)
        ],
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
    }
    return packet, private


def _submission(packet: dict[str, object], *, observed_suffix: str = "00") -> dict[str, object]:
    cases = packet["cases"]
    assert isinstance(cases, list)
    reviews = []
    for index, case in enumerate(cases):
        assert isinstance(case, dict)
        reviews.append(
            {
                "case_id": case["case_id"],
                "assignment_id": case["assignment_id"],
                "preference": "plan_a",
                "ratings": [
                    {
                        "dimension": dimension.value,
                        "plan_a_score": 4.0,
                        "plan_b_score": 3.0,
                    }
                    for dimension in REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1
                ],
                "confidence": 0.85,
                "observed_at": f"2026-08-19T22:{index:02d}:{observed_suffix}+02:00",
                "algorithm_identity_was_hidden": True,
                "reason_codes": ["auditioned_blind_pair"],
                "activation_authorized": False,
            }
        )
    return {
        "schema": HUMAN_DJ_REVIEW_SUBMISSION_SCHEMA,
        "protocol_version": "human-dj-review-r1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "reviewer_ref": "dj-reviewer-01",
        "reviews": reviews,
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
    }


def test_reviewer_packet_integrity_is_verified_fail_closed() -> None:
    packet, _ = _packet_and_private()
    validated = validate_reviewer_packet(packet)
    assert validated["packet_fingerprint"] == packet["packet_fingerprint"]

    cases = packet["cases"]
    assert isinstance(cases, list) and isinstance(cases[0], dict)
    cases[0]["plan_a"][0] = "Tampered display"
    with pytest.raises(HumanDJReviewExecutionError, match="fingerprint mismatch"):
        validate_reviewer_packet(packet)


def test_workspace_is_blinded_self_contained_and_path_free() -> None:
    packet, _ = _packet_and_private()
    material = build_reviewer_workspace(packet)
    text = material.decode("utf-8")

    assert "Plan A" in text
    assert "Plan B" in text
    assert "transition_smoothness" in text
    assert "Export review evidence JSON" in text
    assert "greedy_recommend_next" not in text
    assert "bounded_beam" not in text
    assert "slot_a_plan_id" not in text
    assert "absolute_path" not in text
    assert "personal_dj_model_training_authorized" in text
    assert "fetch(" not in text
    assert "XMLHttpRequest" not in text
    assert "WebSocket" not in text


def test_submission_ingest_is_append_only_and_exact_retry_is_idempotent(tmp_path: Path) -> None:
    packet, _ = _packet_and_private()
    ledger = HumanDJReviewLedger(tmp_path / "reviews.sqlite")
    submission = _submission(packet)

    first = ingest_review_submission(packet=packet, submission=submission, ledger=ledger)
    second = ingest_review_submission(packet=packet, submission=submission, ledger=ledger)

    assert first["review_count"] == 12
    assert first["review_ids"] == second["review_ids"]
    assert len(ledger.list_for_packet(str(packet["packet_fingerprint"]))) == 12

    changed = _submission(packet, observed_suffix="01")
    with pytest.raises(HumanDJReviewExecutionError, match="only one immutable review"):
        ingest_review_submission(packet=packet, submission=changed, ledger=ledger)

    with sqlite3.connect(tmp_path / "reviews.sqlite") as conn:
        with pytest.raises(sqlite3.DatabaseError, match="immutable"):
            conn.execute("UPDATE human_dj_reviews SET reviewer_ref='other'")


def test_visible_algorithm_identity_review_is_rejected(tmp_path: Path) -> None:
    packet, _ = _packet_and_private()
    submission = _submission(packet)
    reviews = submission["reviews"]
    assert isinstance(reviews, list) and isinstance(reviews[0], dict)
    reviews[0]["algorithm_identity_was_hidden"] = False

    with pytest.raises(HumanDJReviewExecutionError, match="algorithm identity was visible"):
        ingest_review_submission(
            packet=packet,
            submission=submission,
            ledger=HumanDJReviewLedger(tmp_path / "reviews.sqlite"),
        )


def test_aggregate_without_human_reviews_is_incomplete_not_synthetic(tmp_path: Path) -> None:
    packet, private = _packet_and_private()
    aggregate = aggregate_human_dj_review(
        packet=packet,
        private_manifest=private,
        ledger=HumanDJReviewLedger(tmp_path / "reviews.sqlite"),
    )
    report = aggregate["report"]

    assert report["verdict"] == "incomplete"
    assert report["review_count"] == 0
    assert aggregate["activation_authorized"] is False
    assert aggregate["personal_dj_model_training_authorized"] is False
    assert aggregate["musical_superiority_implied"] is False


def test_complete_real_human_evidence_produces_protocol_pass_without_activation(
    tmp_path: Path,
) -> None:
    packet, private = _packet_and_private()
    ledger = HumanDJReviewLedger(tmp_path / "reviews.sqlite")
    ingest_review_submission(packet=packet, submission=_submission(packet), ledger=ledger)

    aggregate = aggregate_human_dj_review(
        packet=packet,
        private_manifest=private,
        ledger=ledger,
    )
    report = aggregate["report"]

    assert report["verdict"] == "pass"
    assert report["case_count"] == 12
    assert report["reviewed_case_count"] == 12
    assert report["review_count"] == 12
    assert report["blind_integrity_rate"] == 1.0
    assert report["dimension_coverage_rate"] == 1.0
    assert report["activation_authorized"] is False
    assert aggregate["activation_authorized"] is False
    assert aggregate["musical_superiority_implied"] is False


def test_private_manifest_must_match_blinded_packet(tmp_path: Path) -> None:
    packet, private = _packet_and_private()
    private["snapshot_ref"] = ["different", "1"]
    with pytest.raises(HumanDJReviewExecutionError, match="snapshot does not match"):
        aggregate_human_dj_review(
            packet=packet,
            private_manifest=private,
            ledger=HumanDJReviewLedger(tmp_path / "reviews.sqlite"),
        )
