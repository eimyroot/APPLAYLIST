from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from services.intelligence.r4_pilot_evidence import (
    HUMAN_DJ_REVIEW_AGGREGATE_SCHEMA,
    R4_PILOT_EVENT_SCHEMA,
    R4_PILOT_PROTOCOL_VERSION,
    R4_PILOT_SURVEY_SCHEMA,
    PilotEvidenceLedger,
    R4PilotEvidenceError,
    build_r4_pilot_report,
    canonical_payload_fingerprint,
    validate_pilot_event,
    validate_pilot_survey,
)


def _event(
    event_type: str,
    *,
    observed_at: str,
    event_ref: str,
    session_id: str = "session-01",
    participant_ref: str = "dj-01",
    object_ref: str | None = None,
) -> dict[str, object]:
    return {
        "schema": R4_PILOT_EVENT_SCHEMA,
        "protocol_version": R4_PILOT_PROTOCOL_VERSION,
        "participant_ref": participant_ref,
        "session_id": session_id,
        "event_ref": event_ref,
        "event_type": event_type,
        "observed_at": observed_at,
        "object_ref": object_ref,
        "metadata": {},
        "cloud_upload_authorized": False,
        "personal_dj_model_training_authorized": False,
        "production_activation_authorized": False,
    }


def _survey(*, observed_at: str = "2026-08-24T19:00:00+02:00") -> dict[str, object]:
    return {
        "schema": R4_PILOT_SURVEY_SCHEMA,
        "protocol_version": R4_PILOT_PROTOCOL_VERSION,
        "participant_ref": "dj-01",
        "survey_ref": "pilot-exit-r1",
        "observed_at": observed_at,
        "willingness_to_pay": "yes",
        "stated_monthly_price_minor": 14900,
        "currency": "CZK",
        "trust_score": 4,
        "explainability_score": 5,
        "note": "Would use this for club-set preparation.",
        "reason_codes": ["saved_time", "clear_explanations"],
        "cloud_upload_authorized": False,
        "personal_dj_model_training_authorized": False,
        "production_activation_authorized": False,
    }


def _human_review_aggregate(verdict: str = "pass") -> dict[str, object]:
    aggregate: dict[str, object] = {
        "schema": HUMAN_DJ_REVIEW_AGGREGATE_SCHEMA,
        "protocol_version": "human-dj-review-r1",
        "packet_fingerprint": "a" * 64,
        "report": {
            "verdict": verdict,
            "case_count": 12,
            "reviewed_case_count": 12 if verdict != "incomplete" else 4,
            "review_count": 12 if verdict != "incomplete" else 4,
            "activation_authorized": False,
        },
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
        "musical_superiority_implied": False,
    }
    aggregate["aggregate_fingerprint"] = canonical_payload_fingerprint(aggregate)
    return aggregate


def _complete_session(
    ledger: PilotEvidenceLedger,
    *,
    session_id: str,
    date: str,
    usable_minute: int,
) -> None:
    participant = "dj-01"
    ledger.record_event(
        _event(
            "import_started",
            observed_at=f"{date}T18:00:00+02:00",
            event_ref=f"{session_id}:import",
            session_id=session_id,
            participant_ref=participant,
        )
    )
    ledger.record_event(
        _event(
            "usable_set_reached",
            observed_at=f"{date}T18:{usable_minute:02d}:00+02:00",
            event_ref=f"{session_id}:usable",
            session_id=session_id,
            participant_ref=participant,
            object_ref=f"revision:{session_id}",
        )
    )
    recommendation_ref = f"recommendation:{session_id}:01"
    ledger.record_event(
        _event(
            "recommendation_presented",
            observed_at=f"{date}T18:{usable_minute + 1:02d}:00+02:00",
            event_ref=f"{session_id}:presented",
            session_id=session_id,
            participant_ref=participant,
            object_ref=recommendation_ref,
        )
    )
    ledger.record_event(
        _event(
            "recommendation_inspected",
            observed_at=f"{date}T18:{usable_minute + 2:02d}:00+02:00",
            event_ref=f"{session_id}:inspected",
            session_id=session_id,
            participant_ref=participant,
            object_ref=recommendation_ref,
        )
    )
    ledger.record_event(
        _event(
            "recommendation_accepted",
            observed_at=f"{date}T18:{usable_minute + 3:02d}:00+02:00",
            event_ref=f"{session_id}:accepted",
            session_id=session_id,
            participant_ref=participant,
            object_ref=recommendation_ref,
        )
    )
    ledger.record_event(
        _event(
            "export_completed",
            observed_at=f"{date}T18:{usable_minute + 9:02d}:00+02:00",
            event_ref=f"{session_id}:export",
            session_id=session_id,
            participant_ref=participant,
            object_ref=f"revision:{session_id}",
        )
    )


def test_event_and_survey_validation_are_fail_closed() -> None:
    event = _event(
        "import_started",
        observed_at="2026-08-17T18:00:00+02:00",
        event_ref="event-01",
    )
    assert validate_pilot_event(event)["observed_at"].endswith("+02:00")

    naive = dict(event)
    naive["observed_at"] = "2026-08-17T18:00:00"
    with pytest.raises(R4PilotEvidenceError, match="timezone offset"):
        validate_pilot_event(naive)

    unsafe = dict(event)
    unsafe["cloud_upload_authorized"] = True
    with pytest.raises(R4PilotEvidenceError, match="must be false"):
        validate_pilot_event(unsafe)

    survey = _survey()
    assert validate_pilot_survey(survey)["currency"] == "CZK"
    bad_price = dict(survey)
    bad_price["currency"] = None
    with pytest.raises(R4PilotEvidenceError, match="currency"):
        validate_pilot_survey(bad_price)


def test_append_only_exact_retry_and_conflicting_retry(tmp_path: Path) -> None:
    ledger = PilotEvidenceLedger(tmp_path / "pilot.sqlite")
    event = _event(
        "import_started",
        observed_at="2026-08-17T18:00:00+02:00",
        event_ref="event-01",
    )

    first = ledger.record_event(event)
    second = ledger.record_event(event)
    assert first["record_id"] == second["record_id"]
    assert len(ledger.list_events()) == 1

    conflict = dict(event)
    conflict["observed_at"] = "2026-08-17T18:00:01+02:00"
    with pytest.raises(R4PilotEvidenceError, match="conflicting retry"):
        ledger.record_event(conflict)

    with sqlite3.connect(tmp_path / "pilot.sqlite") as conn:
        with pytest.raises(sqlite3.DatabaseError, match="immutable"):
            conn.execute("UPDATE pilot_events SET participant_ref='other'")
        with pytest.raises(sqlite3.DatabaseError, match="immutable"):
            conn.execute("DELETE FROM pilot_events")


def test_recommendation_and_preparation_correlation_fail_closed(tmp_path: Path) -> None:
    ledger = PilotEvidenceLedger(tmp_path / "pilot.sqlite")
    recommendation = "recommendation:01"

    with pytest.raises(R4PilotEvidenceError, match="prior recommendation_presented"):
        ledger.record_event(
            _event(
                "recommendation_inspected",
                observed_at="2026-08-17T18:02:00+02:00",
                event_ref="inspect-01",
                object_ref=recommendation,
            )
        )

    with pytest.raises(R4PilotEvidenceError, match="prior import_started"):
        ledger.record_event(
            _event(
                "usable_set_reached",
                observed_at="2026-08-17T18:03:00+02:00",
                event_ref="usable-01",
            )
        )

    ledger.record_event(
        _event(
            "recommendation_presented",
            observed_at="2026-08-17T18:01:00+02:00",
            event_ref="present-01",
            object_ref=recommendation,
        )
    )
    with pytest.raises(R4PilotEvidenceError, match="prior recommendation_inspected"):
        ledger.record_event(
            _event(
                "recommendation_accepted",
                observed_at="2026-08-17T18:02:00+02:00",
                event_ref="accept-too-early",
                object_ref=recommendation,
            )
        )
    ledger.record_event(
        _event(
            "recommendation_inspected",
            observed_at="2026-08-17T18:02:00+02:00",
            event_ref="inspect-02",
            object_ref=recommendation,
        )
    )
    ledger.record_event(
        _event(
            "recommendation_accepted",
            observed_at="2026-08-17T18:03:00+02:00",
            event_ref="accept-01",
            object_ref=recommendation,
        )
    )
    with pytest.raises(R4PilotEvidenceError, match="only one immutable decision"):
        ledger.record_event(
            _event(
                "recommendation_rejected",
                observed_at="2026-08-17T18:04:00+02:00",
                event_ref="reject-01",
                object_ref=recommendation,
            )
        )


def test_empty_or_single_week_evidence_is_incomplete(tmp_path: Path) -> None:
    ledger = PilotEvidenceLedger(tmp_path / "pilot.sqlite")
    empty = build_r4_pilot_report(ledger=ledger)
    assert empty["evidence_state"] == "INCOMPLETE"
    assert empty["product_decision"] == "UNDECIDED"
    assert empty["metric_coverage"]["repeat_weekly_use"] is False
    assert empty["production_activation_authorized"] is False

    _complete_session(ledger, session_id="session-01", date="2026-08-17", usable_minute=10)
    single_week = build_r4_pilot_report(
        ledger=ledger,
        human_review_aggregate=_human_review_aggregate(),
    )
    assert single_week["metrics"]["repeat_weekly_use"]["assessable"] is False
    assert single_week["evidence_state"] == "INCOMPLETE"


def test_complete_two_week_fixture_is_ready_for_human_decision_not_auto_go(
    tmp_path: Path,
) -> None:
    ledger = PilotEvidenceLedger(tmp_path / "pilot.sqlite")
    _complete_session(ledger, session_id="session-01", date="2026-08-17", usable_minute=10)
    _complete_session(ledger, session_id="session-02", date="2026-08-24", usable_minute=5)

    for index, event_type in enumerate(("manual_reorder", "manual_replace", "manual_lock"), 1):
        ledger.record_event(
            _event(
                event_type,
                observed_at=f"2026-08-24T18:{10 + index:02d}:00+02:00",
                event_ref=f"session-02:{event_type}",
                session_id="session-02",
                object_ref="revision:session-02",
            )
        )
    ledger.record_survey(_survey())

    report = build_r4_pilot_report(
        ledger=ledger,
        human_review_aggregate=_human_review_aggregate("pass"),
    )
    metrics = report["metrics"]

    assert report["evidence_state"] == "READY_FOR_HUMAN_DECISION"
    assert report["product_decision"] == "UNDECIDED"
    assert report["product_metric_coverage_complete"] is True
    assert report["human_dj_review_complete"] is True
    assert metrics["time_import_to_usable_set"]["sample_count"] == 2
    assert metrics["time_import_to_usable_set"]["median_seconds"] == 450.0
    assert metrics["recommendation_inspection"]["inspection_rate"] == 1.0
    assert metrics["recommendation_decision"]["acceptance_rate"] == 1.0
    assert metrics["manual_edit_frequency_per_import_session"]["reorder_per_session"] == 0.5
    assert metrics["manual_edit_frequency_per_import_session"]["replace_per_session"] == 0.5
    assert metrics["manual_edit_frequency_per_import_session"]["lock_per_session"] == 0.5
    assert metrics["export_completion"]["completion_rate"] == 1.0
    assert metrics["repeat_weekly_use"]["repeat_rate"] == 1.0
    assert metrics["willingness_to_pay"]["yes_rate"] == 1.0
    assert metrics["willingness_to_pay"]["stated_price_by_currency"]["CZK"][
        "median_monthly_price_minor"
    ] == 14900.0
    assert metrics["trust_explainability"]["mean_trust_score"] == 4.0
    assert metrics["trust_explainability"]["mean_explainability_score"] == 5.0
    assert report["optimizer_ranking_activation_authorized"] is False
    assert report["personal_dj_model_training_authorized"] is False
    assert report["production_activation_authorized"] is False
    assert report["musical_superiority_implied"] is False


def test_human_review_binding_is_integrity_checked_and_incomplete_blocks_readiness(
    tmp_path: Path,
) -> None:
    ledger = PilotEvidenceLedger(tmp_path / "pilot.sqlite")
    _complete_session(ledger, session_id="session-01", date="2026-08-17", usable_minute=10)
    _complete_session(ledger, session_id="session-02", date="2026-08-24", usable_minute=5)
    ledger.record_survey(_survey())

    incomplete = build_r4_pilot_report(
        ledger=ledger,
        human_review_aggregate=_human_review_aggregate("incomplete"),
    )
    assert incomplete["human_dj_review_complete"] is False
    assert incomplete["evidence_state"] == "INCOMPLETE"

    tampered = _human_review_aggregate("pass")
    report = tampered["report"]
    assert isinstance(report, dict)
    report["review_count"] = 99
    with pytest.raises(R4PilotEvidenceError, match="fingerprint mismatch"):
        build_r4_pilot_report(ledger=ledger, human_review_aggregate=tampered)
