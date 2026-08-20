from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import statistics
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

R4_PILOT_PROTOCOL_VERSION = "r4-bounded-dj-pilot-r1"
R4_PILOT_EVENT_SCHEMA = "applaylist-r4-pilot-event-r1"
R4_PILOT_SURVEY_SCHEMA = "applaylist-r4-pilot-survey-r1"
R4_PILOT_REPORT_SCHEMA = "applaylist-r4-pilot-report-r1"
R4_PILOT_RECEIPT_SCHEMA = "applaylist-r4-pilot-ingest-receipt-r1"
HUMAN_DJ_REVIEW_AGGREGATE_SCHEMA = "applaylist-human-dj-review-aggregate-r1"

R4_PILOT_EVENT_TYPES = (
    "import_started",
    "usable_set_reached",
    "recommendation_presented",
    "recommendation_inspected",
    "recommendation_accepted",
    "recommendation_rejected",
    "manual_reorder",
    "manual_replace",
    "manual_lock",
    "export_completed",
)
R4_PILOT_WILLINGNESS_TO_PAY = ("yes", "no", "unsure")

_RECOMMENDATION_EVENTS = frozenset(
    {
        "recommendation_presented",
        "recommendation_inspected",
        "recommendation_accepted",
        "recommendation_rejected",
    }
)
_SINGLETON_SESSION_EVENTS = frozenset({"import_started", "usable_set_reached"})
_AUTHORITY_KEYS = (
    "cloud_upload_authorized",
    "personal_dj_model_training_authorized",
    "production_activation_authorized",
)


class R4PilotEvidenceError(ValueError):
    """Fail-closed error for bounded R4 pilot evidence."""


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        + "\n"
    ).encode("utf-8")


def canonical_payload_fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _token(value: object, field: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str):
        raise R4PilotEvidenceError(f"{field} must be text")
    normalized = value.strip()
    if (
        not normalized
        or normalized != value
        or len(normalized) > maximum
        or any(ord(character) < 32 for character in normalized)
    ):
        raise R4PilotEvidenceError(f"{field} is invalid")
    return normalized


def _optional_token(value: object, field: str, *, maximum: int = 256) -> str | None:
    if value is None:
        return None
    return _token(value, field, maximum=maximum)


def _bounded_note(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise R4PilotEvidenceError("note must be text or null")
    normalized = value.strip()
    if (
        normalized != value
        or len(normalized) > 1000
        or any(ord(character) < 32 and character not in "\n\t" for character in normalized)
    ):
        raise R4PilotEvidenceError("note is invalid")
    return normalized or None


def _timestamp(value: object, field: str = "observed_at") -> tuple[str, datetime]:
    text = _token(value, field, maximum=64)
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise R4PilotEvidenceError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise R4PilotEvidenceError(f"{field} must include a timezone offset")
    return parsed.isoformat(), parsed


def _authority_false(raw: Mapping[str, Any]) -> None:
    for key in _AUTHORITY_KEYS:
        if raw.get(key) is not False:
            raise R4PilotEvidenceError(f"{key} must be false")


def _metadata(value: object) -> dict[str, str | int | float | bool]:
    if value is None:
        return {}
    if not isinstance(value, Mapping) or len(value) > 12:
        raise R4PilotEvidenceError("metadata must be an object with at most 12 entries")
    normalized: dict[str, str | int | float | bool] = {}
    for raw_key, raw_value in value.items():
        key = _token(raw_key, "metadata key", maximum=64)
        if isinstance(raw_value, bool):
            normalized[key] = raw_value
        elif isinstance(raw_value, int):
            normalized[key] = raw_value
        elif isinstance(raw_value, float):
            if not math.isfinite(raw_value):
                raise R4PilotEvidenceError("metadata numbers must be finite")
            normalized[key] = raw_value
        elif isinstance(raw_value, str):
            normalized[key] = _token(raw_value, f"metadata[{key}]", maximum=256)
        else:
            raise R4PilotEvidenceError("metadata values must be bounded scalars")
    return dict(sorted(normalized.items()))


def validate_pilot_event(raw: Mapping[str, Any]) -> dict[str, Any]:
    expected_keys = {
        "schema",
        "protocol_version",
        "participant_ref",
        "session_id",
        "event_ref",
        "event_type",
        "observed_at",
        "object_ref",
        "metadata",
        *_AUTHORITY_KEYS,
    }
    if set(raw) != expected_keys:
        raise R4PilotEvidenceError("pilot event has unexpected or missing fields")
    if raw.get("schema") != R4_PILOT_EVENT_SCHEMA:
        raise R4PilotEvidenceError("unsupported pilot event schema")
    if raw.get("protocol_version") != R4_PILOT_PROTOCOL_VERSION:
        raise R4PilotEvidenceError("unsupported pilot protocol version")
    _authority_false(raw)

    event_type = _token(raw.get("event_type"), "event_type", maximum=64)
    if event_type not in R4_PILOT_EVENT_TYPES:
        raise R4PilotEvidenceError("unsupported pilot event type")
    object_ref = _optional_token(raw.get("object_ref"), "object_ref", maximum=256)
    if event_type in _RECOMMENDATION_EVENTS and object_ref is None:
        raise R4PilotEvidenceError("recommendation events require object_ref")
    observed_at, _ = _timestamp(raw.get("observed_at"))

    return {
        "schema": R4_PILOT_EVENT_SCHEMA,
        "protocol_version": R4_PILOT_PROTOCOL_VERSION,
        "participant_ref": _token(raw.get("participant_ref"), "participant_ref"),
        "session_id": _token(raw.get("session_id"), "session_id"),
        "event_ref": _token(raw.get("event_ref"), "event_ref"),
        "event_type": event_type,
        "observed_at": observed_at,
        "object_ref": object_ref,
        "metadata": _metadata(raw.get("metadata")),
        "cloud_upload_authorized": False,
        "personal_dj_model_training_authorized": False,
        "production_activation_authorized": False,
    }


def _integer_score(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise R4PilotEvidenceError(f"{field} must be an integer from 1 to 5")
    return value


def _reason_codes(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 8:
        raise R4PilotEvidenceError("reason_codes must be an array with at most 8 entries")
    codes = [_token(item, "reason_code", maximum=64) for item in value]
    if len(set(codes)) != len(codes):
        raise R4PilotEvidenceError("reason_codes must be unique")
    return codes


def validate_pilot_survey(raw: Mapping[str, Any]) -> dict[str, Any]:
    expected_keys = {
        "schema",
        "protocol_version",
        "participant_ref",
        "survey_ref",
        "observed_at",
        "willingness_to_pay",
        "stated_monthly_price_minor",
        "currency",
        "trust_score",
        "explainability_score",
        "note",
        "reason_codes",
        *_AUTHORITY_KEYS,
    }
    if set(raw) != expected_keys:
        raise R4PilotEvidenceError("pilot survey has unexpected or missing fields")
    if raw.get("schema") != R4_PILOT_SURVEY_SCHEMA:
        raise R4PilotEvidenceError("unsupported pilot survey schema")
    if raw.get("protocol_version") != R4_PILOT_PROTOCOL_VERSION:
        raise R4PilotEvidenceError("unsupported pilot protocol version")
    _authority_false(raw)

    willingness = _token(raw.get("willingness_to_pay"), "willingness_to_pay", maximum=16)
    if willingness not in R4_PILOT_WILLINGNESS_TO_PAY:
        raise R4PilotEvidenceError("unsupported willingness_to_pay value")

    raw_price = raw.get("stated_monthly_price_minor")
    raw_currency = raw.get("currency")
    if raw_price is None:
        price_minor = None
        if raw_currency is not None:
            raise R4PilotEvidenceError("currency requires stated_monthly_price_minor")
        currency = None
    else:
        if isinstance(raw_price, bool) or not isinstance(raw_price, int):
            raise R4PilotEvidenceError("stated_monthly_price_minor must be an integer or null")
        if raw_price < 0 or raw_price > 100_000_000:
            raise R4PilotEvidenceError("stated_monthly_price_minor is out of bounds")
        price_minor = raw_price
        currency = _token(raw_currency, "currency", maximum=3)
        if len(currency) != 3 or currency.upper() != currency or not currency.isalpha():
            raise R4PilotEvidenceError("currency must be a three-letter uppercase token")

    observed_at, _ = _timestamp(raw.get("observed_at"))
    return {
        "schema": R4_PILOT_SURVEY_SCHEMA,
        "protocol_version": R4_PILOT_PROTOCOL_VERSION,
        "participant_ref": _token(raw.get("participant_ref"), "participant_ref"),
        "survey_ref": _token(raw.get("survey_ref"), "survey_ref"),
        "observed_at": observed_at,
        "willingness_to_pay": willingness,
        "stated_monthly_price_minor": price_minor,
        "currency": currency,
        "trust_score": _integer_score(raw.get("trust_score"), "trust_score"),
        "explainability_score": _integer_score(
            raw.get("explainability_score"), "explainability_score"
        ),
        "note": _bounded_note(raw.get("note")),
        "reason_codes": _reason_codes(raw.get("reason_codes")),
        "cloud_upload_authorized": False,
        "personal_dj_model_training_authorized": False,
        "production_activation_authorized": False,
    }


def _record_identity(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}:{canonical_payload_fingerprint(payload)}"


class PilotEvidenceLedger:
    """Local append-only SQLite ledger for bounded R4 pilot evidence."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _initialize(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS pilot_events (
                    event_id TEXT PRIMARY KEY,
                    participant_ref TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    event_ref TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    object_ref TEXT,
                    event_json TEXT NOT NULL,
                    UNIQUE(participant_ref, session_id, event_ref)
                );
                CREATE TABLE IF NOT EXISTS pilot_surveys (
                    survey_id TEXT PRIMARY KEY,
                    participant_ref TEXT NOT NULL,
                    survey_ref TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    survey_json TEXT NOT NULL,
                    UNIQUE(participant_ref, survey_ref)
                );
                CREATE TRIGGER IF NOT EXISTS pilot_events_no_update
                BEFORE UPDATE ON pilot_events
                BEGIN SELECT RAISE(ABORT, 'pilot evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS pilot_events_no_delete
                BEFORE DELETE ON pilot_events
                BEGIN SELECT RAISE(ABORT, 'pilot evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS pilot_surveys_no_update
                BEFORE UPDATE ON pilot_surveys
                BEGIN SELECT RAISE(ABORT, 'pilot evidence is immutable'); END;
                CREATE TRIGGER IF NOT EXISTS pilot_surveys_no_delete
                BEFORE DELETE ON pilot_surveys
                BEGIN SELECT RAISE(ABORT, 'pilot evidence is immutable'); END;
                """
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _event_time(payload: Mapping[str, Any]) -> datetime:
        return _timestamp(payload["observed_at"])[1]

    def _prior_event(
        self,
        conn: sqlite3.Connection,
        *,
        participant_ref: str,
        session_id: str,
        event_type: str,
        object_ref: str | None = None,
    ) -> dict[str, Any] | None:
        sql = (
            "SELECT event_json FROM pilot_events "
            "WHERE participant_ref=? AND session_id=? AND event_type=?"
        )
        params: list[object] = [participant_ref, session_id, event_type]
        if object_ref is not None:
            sql += " AND object_ref=?"
            params.append(object_ref)
        sql += " ORDER BY observed_at, event_id LIMIT 1"
        row = conn.execute(sql, params).fetchone()
        return json.loads(row["event_json"]) if row else None

    def _validate_event_correlation(
        self,
        conn: sqlite3.Connection,
        payload: Mapping[str, Any],
    ) -> None:
        participant_ref = str(payload["participant_ref"])
        session_id = str(payload["session_id"])
        event_type = str(payload["event_type"])
        observed = self._event_time(payload)

        if event_type in _SINGLETON_SESSION_EVENTS:
            prior = self._prior_event(
                conn,
                participant_ref=participant_ref,
                session_id=session_id,
                event_type=event_type,
            )
            if prior is not None:
                raise R4PilotEvidenceError(
                    f"{event_type} may occur only once per participant/session"
                )

        if event_type == "usable_set_reached":
            imported = self._prior_event(
                conn,
                participant_ref=participant_ref,
                session_id=session_id,
                event_type="import_started",
            )
            if imported is None:
                raise R4PilotEvidenceError("usable_set_reached requires prior import_started")
            if observed < self._event_time(imported):
                raise R4PilotEvidenceError("usable_set_reached cannot precede import_started")

        if event_type not in _RECOMMENDATION_EVENTS:
            return

        object_ref = str(payload["object_ref"])
        presented = self._prior_event(
            conn,
            participant_ref=participant_ref,
            session_id=session_id,
            event_type="recommendation_presented",
            object_ref=object_ref,
        )
        if event_type == "recommendation_presented":
            if presented is not None:
                raise R4PilotEvidenceError(
                    "recommendation presentation object_ref must be unique per session"
                )
            return
        if presented is None:
            raise R4PilotEvidenceError(
                f"{event_type} requires prior recommendation_presented for object_ref"
            )
        if observed < self._event_time(presented):
            raise R4PilotEvidenceError(f"{event_type} cannot precede recommendation_presented")

        inspected = self._prior_event(
            conn,
            participant_ref=participant_ref,
            session_id=session_id,
            event_type="recommendation_inspected",
            object_ref=object_ref,
        )
        if event_type == "recommendation_inspected":
            if inspected is not None:
                raise R4PilotEvidenceError(
                    "recommendation inspection may occur only once per presentation"
                )
            return
        if inspected is None:
            raise R4PilotEvidenceError(
                f"{event_type} requires prior recommendation_inspected for object_ref"
            )
        if observed < self._event_time(inspected):
            raise R4PilotEvidenceError(f"{event_type} cannot precede recommendation_inspected")

        accepted = self._prior_event(
            conn,
            participant_ref=participant_ref,
            session_id=session_id,
            event_type="recommendation_accepted",
            object_ref=object_ref,
        )
        rejected = self._prior_event(
            conn,
            participant_ref=participant_ref,
            session_id=session_id,
            event_type="recommendation_rejected",
            object_ref=object_ref,
        )
        if accepted is not None or rejected is not None:
            raise R4PilotEvidenceError("recommendation may have only one immutable decision")

    def record_event(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        payload = validate_pilot_event(raw)
        event_id = _record_identity("pilot-event", payload)
        event_json = _canonical_json_bytes(payload).decode("utf-8")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT event_id, event_json FROM pilot_events
                WHERE participant_ref=? AND session_id=? AND event_ref=?
                """,
                (
                    payload["participant_ref"],
                    payload["session_id"],
                    payload["event_ref"],
                ),
            ).fetchone()
            if existing is not None:
                if existing["event_json"] == event_json:
                    conn.commit()
                    return self._receipt("event", str(existing["event_id"]), payload)
                raise R4PilotEvidenceError("conflicting retry for immutable pilot event_ref")

            self._validate_event_correlation(conn, payload)
            conn.execute(
                """
                INSERT INTO pilot_events(
                    event_id, participant_ref, session_id, event_ref,
                    event_type, observed_at, object_ref, event_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    payload["participant_ref"],
                    payload["session_id"],
                    payload["event_ref"],
                    payload["event_type"],
                    payload["observed_at"],
                    payload["object_ref"],
                    event_json,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self._receipt("event", event_id, payload)

    def record_survey(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        payload = validate_pilot_survey(raw)
        survey_id = _record_identity("pilot-survey", payload)
        survey_json = _canonical_json_bytes(payload).decode("utf-8")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT survey_id, survey_json FROM pilot_surveys
                WHERE participant_ref=? AND survey_ref=?
                """,
                (payload["participant_ref"], payload["survey_ref"]),
            ).fetchone()
            if existing is not None:
                if existing["survey_json"] == survey_json:
                    conn.commit()
                    return self._receipt("survey", str(existing["survey_id"]), payload)
                raise R4PilotEvidenceError("conflicting retry for immutable pilot survey_ref")
            conn.execute(
                """
                INSERT INTO pilot_surveys(
                    survey_id, participant_ref, survey_ref, observed_at, survey_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    survey_id,
                    payload["participant_ref"],
                    payload["survey_ref"],
                    payload["observed_at"],
                    survey_json,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self._receipt("survey", survey_id, payload)

    @staticmethod
    def _receipt(kind: str, record_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        receipt = {
            "schema": R4_PILOT_RECEIPT_SCHEMA,
            "protocol_version": R4_PILOT_PROTOCOL_VERSION,
            "kind": kind,
            "record_id": record_id,
            "participant_ref": payload["participant_ref"],
            "observed_at": payload["observed_at"],
            "cloud_upload_authorized": False,
            "personal_dj_model_training_authorized": False,
            "production_activation_authorized": False,
        }
        receipt["receipt_fingerprint"] = canonical_payload_fingerprint(receipt)
        return receipt

    def list_events(self) -> tuple[dict[str, Any], ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT event_json FROM pilot_events ORDER BY observed_at, event_id"
            ).fetchall()
        finally:
            conn.close()
        return tuple(json.loads(row["event_json"]) for row in rows)

    def list_surveys(self) -> tuple[dict[str, Any], ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT survey_json FROM pilot_surveys ORDER BY observed_at, survey_id"
            ).fetchall()
        finally:
            conn.close()
        return tuple(json.loads(row["survey_json"]) for row in rows)


def validate_human_review_aggregate(raw: Mapping[str, Any]) -> dict[str, Any]:
    if raw.get("schema") != HUMAN_DJ_REVIEW_AGGREGATE_SCHEMA:
        raise R4PilotEvidenceError("unsupported Human DJ Review aggregate schema")
    if raw.get("activation_authorized") is not False:
        raise R4PilotEvidenceError("Human DJ Review aggregate cannot authorize activation")
    if raw.get("personal_dj_model_training_authorized") is not False:
        raise R4PilotEvidenceError("Human DJ Review aggregate cannot authorize PDM training")
    if raw.get("musical_superiority_implied") is not False:
        raise R4PilotEvidenceError("Human DJ Review aggregate cannot imply musical superiority")

    supplied_fingerprint = _token(
        raw.get("aggregate_fingerprint"), "aggregate_fingerprint", maximum=128
    )
    material = dict(raw)
    material.pop("aggregate_fingerprint", None)
    if canonical_payload_fingerprint(material) != supplied_fingerprint:
        raise R4PilotEvidenceError("Human DJ Review aggregate fingerprint mismatch")

    report = raw.get("report")
    if not isinstance(report, Mapping):
        raise R4PilotEvidenceError("Human DJ Review aggregate report must be an object")
    verdict = str(report.get("verdict", "")).strip().lower()
    if verdict not in {"pass", "fail", "incomplete"}:
        raise R4PilotEvidenceError("Human DJ Review aggregate verdict is invalid")
    if report.get("activation_authorized") is not False:
        raise R4PilotEvidenceError("Human DJ Review report cannot authorize activation")

    def _optional_count(key: str) -> int | None:
        value = report.get(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise R4PilotEvidenceError(f"Human DJ Review {key} is invalid")
        return value

    return {
        "protocol_version": str(raw.get("protocol_version", "")),
        "packet_fingerprint": str(raw.get("packet_fingerprint", "")),
        "aggregate_fingerprint": supplied_fingerprint,
        "verdict": verdict,
        "case_count": _optional_count("case_count"),
        "reviewed_case_count": _optional_count("reviewed_case_count"),
        "review_count": _optional_count("review_count"),
        "musical_superiority_implied": False,
        "activation_authorized": False,
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _mean(values: Sequence[int | float]) -> float | None:
    if not values:
        return None
    return round(statistics.fmean(values), 6)


def _median(values: Sequence[int | float]) -> float | None:
    if not values:
        return None
    return round(float(statistics.median(values)), 6)


def build_r4_pilot_report(
    *,
    ledger: PilotEvidenceLedger,
    human_review_aggregate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    events = ledger.list_events()
    surveys = ledger.list_surveys()
    event_counts = Counter(str(item["event_type"]) for item in events)
    session_events: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    participant_weeks: dict[str, set[tuple[int, int]]] = defaultdict(set)
    pilot_weeks: set[tuple[int, int]] = set()

    for event in events:
        key = (str(event["participant_ref"]), str(event["session_id"]))
        session_events[key].append(event)
        observed = _timestamp(event["observed_at"])[1]
        iso = observed.isocalendar()
        week = (iso.year, iso.week)
        participant_weeks[str(event["participant_ref"])].add(week)
        pilot_weeks.add(week)

    import_sessions = 0
    prep_durations: list[float] = []
    export_sessions = 0
    edit_counts = {
        "manual_reorder": event_counts["manual_reorder"],
        "manual_replace": event_counts["manual_replace"],
        "manual_lock": event_counts["manual_lock"],
    }
    for items in session_events.values():
        by_type = {str(item["event_type"]): item for item in items}
        imported = by_type.get("import_started")
        usable = by_type.get("usable_set_reached")
        if imported is not None:
            import_sessions += 1
            if usable is not None:
                start = _timestamp(imported["observed_at"])[1]
                end = _timestamp(usable["observed_at"])[1]
                seconds = (end - start).total_seconds()
                if seconds < 0:
                    raise R4PilotEvidenceError("negative preparation duration in immutable ledger")
                prep_durations.append(seconds)
            if any(item["event_type"] == "export_completed" for item in items):
                export_sessions += 1

    presented = event_counts["recommendation_presented"]
    inspected = event_counts["recommendation_inspected"]
    accepted = event_counts["recommendation_accepted"]
    rejected = event_counts["recommendation_rejected"]
    decisions = accepted + rejected

    event_participants = set(participant_weeks)
    survey_participants = {str(item["participant_ref"]) for item in surveys}
    participants = sorted(event_participants | survey_participants)
    repeat_assessable = len(pilot_weeks) >= 2 and bool(event_participants)
    repeat_participants = sum(
        1 for participant in event_participants if len(participant_weeks[participant]) >= 2
    )

    willingness_counts = Counter(str(item["willingness_to_pay"]) for item in surveys)
    price_by_currency: dict[str, list[int]] = defaultdict(list)
    for survey in surveys:
        price = survey["stated_monthly_price_minor"]
        currency = survey["currency"]
        if price is not None and currency is not None:
            price_by_currency[str(currency)].append(int(price))
    price_summary = {
        currency: {
            "response_count": len(values),
            "median_monthly_price_minor": _median(values),
        }
        for currency, values in sorted(price_by_currency.items())
    }

    coverage = {
        "time_import_to_usable_set": bool(prep_durations),
        "recommendation_inspection_rate": presented > 0,
        "recommendation_accept_reject_rate": decisions > 0,
        "manual_reorder_frequency": import_sessions > 0,
        "manual_replace_frequency": import_sessions > 0,
        "lock_frequency": import_sessions > 0,
        "export_completion_rate": import_sessions > 0,
        "repeat_weekly_use": repeat_assessable,
        "willingness_to_pay": bool(surveys),
        "trust_explainability": bool(surveys),
    }
    product_metric_coverage_complete = all(coverage.values())

    human_summary = (
        validate_human_review_aggregate(human_review_aggregate)
        if human_review_aggregate is not None
        else None
    )
    human_review_complete = (
        human_summary is not None and human_summary["verdict"] in {"pass", "fail"}
    )
    evidence_state = (
        "READY_FOR_HUMAN_DECISION"
        if product_metric_coverage_complete and human_review_complete
        else "INCOMPLETE"
    )

    report: dict[str, Any] = {
        "schema": R4_PILOT_REPORT_SCHEMA,
        "protocol_version": R4_PILOT_PROTOCOL_VERSION,
        "evidence_state": evidence_state,
        "product_decision": "UNDECIDED",
        "participant_count": len(participants),
        "session_count": len(session_events),
        "event_count": len(events),
        "survey_count": len(surveys),
        "event_counts": {
            event_type: event_counts[event_type] for event_type in R4_PILOT_EVENT_TYPES
        },
        "metrics": {
            "time_import_to_usable_set": {
                "sample_count": len(prep_durations),
                "median_seconds": _median(prep_durations),
                "mean_seconds": _mean(prep_durations),
            },
            "recommendation_inspection": {
                "presented_count": presented,
                "inspected_count": inspected,
                "inspection_rate": _ratio(inspected, presented),
            },
            "recommendation_decision": {
                "accepted_count": accepted,
                "rejected_count": rejected,
                "decision_count": decisions,
                "acceptance_rate": _ratio(accepted, decisions),
                "rejection_rate": _ratio(rejected, decisions),
            },
            "manual_edit_frequency_per_import_session": {
                "import_session_count": import_sessions,
                "reorder_count": edit_counts["manual_reorder"],
                "replace_count": edit_counts["manual_replace"],
                "lock_count": edit_counts["manual_lock"],
                "reorder_per_session": _ratio(edit_counts["manual_reorder"], import_sessions),
                "replace_per_session": _ratio(edit_counts["manual_replace"], import_sessions),
                "lock_per_session": _ratio(edit_counts["manual_lock"], import_sessions),
            },
            "export_completion": {
                "import_session_count": import_sessions,
                "export_completed_session_count": export_sessions,
                "completion_rate": _ratio(export_sessions, import_sessions),
            },
            "repeat_weekly_use": {
                "assessable": repeat_assessable,
                "pilot_iso_week_count": len(pilot_weeks),
                "participant_with_usage_count": len(event_participants),
                "repeat_participant_count": repeat_participants,
                "repeat_rate": (
                    _ratio(repeat_participants, len(event_participants))
                    if repeat_assessable
                    else None
                ),
            },
            "willingness_to_pay": {
                "response_count": len(surveys),
                "yes_count": willingness_counts["yes"],
                "no_count": willingness_counts["no"],
                "unsure_count": willingness_counts["unsure"],
                "yes_rate": _ratio(willingness_counts["yes"], len(surveys)),
                "stated_price_by_currency": price_summary,
            },
            "trust_explainability": {
                "response_count": len(surveys),
                "mean_trust_score": _mean([int(item["trust_score"]) for item in surveys]),
                "mean_explainability_score": _mean(
                    [int(item["explainability_score"]) for item in surveys]
                ),
            },
        },
        "metric_coverage": coverage,
        "product_metric_coverage_complete": product_metric_coverage_complete,
        "human_dj_review": human_summary,
        "human_dj_review_complete": human_review_complete,
        "cloud_upload_authorized": False,
        "optimizer_ranking_activation_authorized": False,
        "personal_dj_model_training_authorized": False,
        "production_activation_authorized": False,
        "musical_superiority_implied": False,
    }
    report["report_fingerprint"] = canonical_payload_fingerprint(report)
    return report


__all__ = [
    "HUMAN_DJ_REVIEW_AGGREGATE_SCHEMA",
    "R4_PILOT_EVENT_SCHEMA",
    "R4_PILOT_EVENT_TYPES",
    "R4_PILOT_PROTOCOL_VERSION",
    "R4_PILOT_RECEIPT_SCHEMA",
    "R4_PILOT_REPORT_SCHEMA",
    "R4_PILOT_SURVEY_SCHEMA",
    "R4_PILOT_WILLINGNESS_TO_PAY",
    "PilotEvidenceLedger",
    "R4PilotEvidenceError",
    "build_r4_pilot_report",
    "canonical_payload_fingerprint",
    "validate_human_review_aggregate",
    "validate_pilot_event",
    "validate_pilot_survey",
]
