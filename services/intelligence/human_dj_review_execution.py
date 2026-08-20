from __future__ import annotations

import hashlib
import html
import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from core.intelligence.curated_real_library_review_contract import (
    HUMAN_DJ_REVIEW_PROTOCOL_VERSION,
    REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1,
    BlindedPlanAssignment,
    CuratedLibrarySnapshot,
    CuratedReviewCase,
    CuratedSetRole,
    HumanDJReview,
    HumanDimensionPairRating,
    HumanPlanPreference,
    ReviewPlanStrategy,
    ReviewableSetPlan,
)
from services.intelligence.curated_real_library_review import (
    evaluate_curated_real_library_human_review_r1,
)

BLIND_REVIEW_PACKET_SCHEMA = "applaylist-blind-human-dj-review-packet-r1"
HUMAN_DJ_REVIEW_SUBMISSION_SCHEMA = "applaylist-human-dj-review-submission-r1"
HUMAN_DJ_REVIEW_AGGREGATE_SCHEMA = "applaylist-human-dj-review-aggregate-r1"
PRIVATE_RUNTIME_EVIDENCE_SCHEMA = "applaylist-private-runtime-music-evidence-r1"

_ALLOWED_PREFERENCES = tuple(item.value for item in HumanPlanPreference)
_REQUIRED_DIMENSIONS = tuple(item.value for item in REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1)


class HumanDJReviewExecutionError(ValueError):
    """Fail-closed error for blinded human DJ review execution evidence."""


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


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _token(value: object, field: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str):
        raise HumanDJReviewExecutionError(f"{field} must be text")
    normalized = value.strip()
    if (
        not normalized
        or normalized != value
        or len(normalized) > maximum
        or any(ord(character) < 32 for character in normalized)
    ):
        raise HumanDJReviewExecutionError(f"{field} is invalid")
    return normalized


def _load_json_object(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise HumanDJReviewExecutionError(f"JSON input not found: {source}")
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise HumanDJReviewExecutionError("JSON input must contain an object")
    return raw


def reviewer_packet_fingerprint(packet: Mapping[str, Any]) -> str:
    """Reproduce the canonical Bundle 54 reviewer-packet fingerprint exactly."""
    material = dict(packet)
    supplied = material.pop("packet_fingerprint", None)
    if supplied is not None and not isinstance(supplied, str):
        raise HumanDJReviewExecutionError("packet_fingerprint must be text")
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def validate_reviewer_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    if packet.get("schema") != BLIND_REVIEW_PACKET_SCHEMA:
        raise HumanDJReviewExecutionError("unsupported blinded reviewer packet schema")
    if packet.get("protocol_version") != HUMAN_DJ_REVIEW_PROTOCOL_VERSION:
        raise HumanDJReviewExecutionError("unsupported human DJ review protocol version")
    if packet.get("algorithm_identity_hidden") is not True:
        raise HumanDJReviewExecutionError("algorithm identity must remain hidden")
    if packet.get("activation_authorized") is not False:
        raise HumanDJReviewExecutionError("reviewer packet cannot authorize activation")
    if packet.get("personal_dj_model_training_authorized") is not False:
        raise HumanDJReviewExecutionError("reviewer packet cannot authorize Personal DJ Model training")

    expected_fingerprint = reviewer_packet_fingerprint(packet)
    if packet.get("packet_fingerprint") != expected_fingerprint:
        raise HumanDJReviewExecutionError("reviewer packet fingerprint mismatch")

    snapshot_ref = packet.get("snapshot_ref")
    if not isinstance(snapshot_ref, list) or len(snapshot_ref) != 2:
        raise HumanDJReviewExecutionError("snapshot_ref must contain exactly two values")
    _token(snapshot_ref[0], "snapshot_ref[0]")
    _token(snapshot_ref[1], "snapshot_ref[1]")

    cases = packet.get("cases")
    if not isinstance(cases, list) or not cases:
        raise HumanDJReviewExecutionError("reviewer packet cases must be a non-empty array")

    case_ids: set[str] = set()
    assignment_ids: set[str] = set()
    normalized_cases: list[dict[str, Any]] = []
    for raw in cases:
        if not isinstance(raw, dict):
            raise HumanDJReviewExecutionError("reviewer case must be an object")
        allowed_keys = {
            "case_id",
            "set_role",
            "assignment_id",
            "plan_a",
            "plan_b",
            "required_review_dimensions",
            "allowed_preference",
        }
        if set(raw) != allowed_keys:
            raise HumanDJReviewExecutionError("reviewer case has unexpected fields")
        case_id = _token(raw["case_id"], "case_id")
        assignment_id = _token(raw["assignment_id"], "assignment_id")
        if case_id in case_ids or assignment_id in assignment_ids:
            raise HumanDJReviewExecutionError("reviewer packet case/assignment identities must be unique")
        case_ids.add(case_id)
        assignment_ids.add(assignment_id)

        try:
            role = CuratedSetRole(str(raw["set_role"])).value
        except ValueError as exc:
            raise HumanDJReviewExecutionError("reviewer case has an unknown set role") from exc

        plans: dict[str, list[str]] = {}
        for slot in ("plan_a", "plan_b"):
            value = raw[slot]
            if not isinstance(value, list) or not value:
                raise HumanDJReviewExecutionError(f"{slot} must be a non-empty array")
            plans[slot] = [_token(item, f"{slot} display name", maximum=512) for item in value]

        dimensions = raw["required_review_dimensions"]
        if not isinstance(dimensions, list) or tuple(dimensions) != _REQUIRED_DIMENSIONS:
            raise HumanDJReviewExecutionError("reviewer case dimensions do not match the R1 protocol")
        preferences = raw["allowed_preference"]
        if not isinstance(preferences, list) or tuple(preferences) != _ALLOWED_PREFERENCES:
            raise HumanDJReviewExecutionError("reviewer case preference choices do not match the R1 protocol")

        normalized_cases.append(
            {
                "case_id": case_id,
                "set_role": role,
                "assignment_id": assignment_id,
                "plan_a": plans["plan_a"],
                "plan_b": plans["plan_b"],
                "required_review_dimensions": list(_REQUIRED_DIMENSIONS),
                "allowed_preference": list(_ALLOWED_PREFERENCES),
            }
        )

    return {
        "schema": BLIND_REVIEW_PACKET_SCHEMA,
        "protocol_version": HUMAN_DJ_REVIEW_PROTOCOL_VERSION,
        "generated_at": _token(packet.get("generated_at"), "generated_at"),
        "snapshot_ref": [str(snapshot_ref[0]), str(snapshot_ref[1])],
        "algorithm_identity_hidden": True,
        "cases": normalized_cases,
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
        "packet_fingerprint": expected_fingerprint,
    }


def build_reviewer_workspace(packet: Mapping[str, Any]) -> bytes:
    validated = validate_reviewer_packet(packet)
    embedded = json.dumps(validated, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    embedded = embedded.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    title = "APPLAYLIST — Blinded Human DJ Review R1"
    template = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{font-family:Inter,system-ui,sans-serif;color-scheme:dark;background:#0b0d12;color:#f5f7fb}
body{max-width:1180px;margin:0 auto;padding:28px}h1{margin-bottom:6px}.muted{color:#aeb6c5}
.case{border:1px solid #2b3340;border-radius:14px;padding:18px;margin:18px 0;background:#111620}
.plans{display:grid;grid-template-columns:1fr 1fr;gap:16px}.plan{border:1px solid #30394a;border-radius:10px;padding:12px}
table{width:100%;border-collapse:collapse;margin-top:12px}th,td{padding:7px;border-bottom:1px solid #252d39;text-align:left}
input,select{background:#0b0f16;color:#fff;border:1px solid #3b4658;border-radius:7px;padding:7px}
button{padding:10px 15px;border:0;border-radius:9px;font-weight:700;cursor:pointer}
.actions{position:sticky;bottom:0;background:#0b0d12;padding:14px 0} .error{color:#ffb4b4}
@media(max-width:780px){.plans{grid-template-columns:1fr}}
</style>
</head>
<body>
<h1>__TITLE__</h1>
<p class="muted">Judge only what you hear and the ordering shown as Plan A / Plan B. Algorithm identity is intentionally hidden.</p>
<label>Reviewer reference <input id="reviewer" autocomplete="off" placeholder="dj-reviewer-01"></label>
<div id="cases"></div>
<p id="status" class="error"></p>
<div class="actions"><button id="export">Export review evidence JSON</button></div>
<script>
"use strict";
const packet=__PACKET__;
const root=document.getElementById("cases");
function node(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n}
function fieldName(caseId,dimension,slot){return `${caseId}::${dimension}::${slot}`}
for(const item of packet.cases){
  const box=node("section");box.className="case";box.dataset.caseId=item.case_id;
  box.append(node("h2",`${item.case_id} · ${item.set_role}`));
  const plans=node("div");plans.className="plans";
  for(const [key,label] of [["plan_a","Plan A"],["plan_b","Plan B"]]){
    const p=node("div");p.className="plan";p.append(node("h3",label));
    const ol=node("ol");for(const track of item[key])ol.append(node("li",track));p.append(ol);plans.append(p);
  }
  box.append(plans);
  const pref=node("select");pref.name=`${item.case_id}::preference`;
  pref.append(new Option("Choose…",""));
  for(const value of item.allowed_preference)pref.append(new Option(value,value));
  const prefLabel=node("label","Preference ");prefLabel.append(pref);box.append(prefLabel);
  const table=node("table");
  const head=node("tr");for(const text of ["Dimension","Plan A","Plan B"])head.append(node("th",text));table.append(head);
  for(const dimension of item.required_review_dimensions){
    const row=node("tr");row.append(node("td",dimension));
    for(const slot of ["a","b"]){
      const cell=node("td");const input=document.createElement("input");input.type="number";input.min="1";input.max="5";input.step="1";
      input.name=fieldName(item.case_id,dimension,slot);cell.append(input);row.append(cell);
    }
    table.append(row);
  }
  box.append(table);
  const confidence=document.createElement("input");confidence.type="number";confidence.min="0";confidence.max="1";confidence.step="0.05";
  confidence.name=`${item.case_id}::confidence`;
  const confidenceLabel=node("label"," Confidence 0–1 ");confidenceLabel.append(confidence);box.append(confidenceLabel);
  root.append(box);
}
function requireValue(selector,message){
  const value=document.querySelector(selector)?.value?.trim();if(!value)throw new Error(message);return value;
}
document.getElementById("export").addEventListener("click",()=>{
  const status=document.getElementById("status");status.textContent="";
  try{
    const reviewer=requireValue("#reviewer","Reviewer reference is required.");
    const reviews=[];
    for(const item of packet.cases){
      const preference=requireValue(`[name="${item.case_id}::preference"]`,`Preference missing for ${item.case_id}.`);
      const ratings=item.required_review_dimensions.map(dimension=>({
        dimension,
        plan_a_score:Number(requireValue(`[name="${fieldName(item.case_id,dimension,"a")}"]`,`Plan A rating missing for ${item.case_id}/${dimension}.`)),
        plan_b_score:Number(requireValue(`[name="${fieldName(item.case_id,dimension,"b")}"]`,`Plan B rating missing for ${item.case_id}/${dimension}.`))
      }));
      if(ratings.some(x=>x.plan_a_score<1||x.plan_a_score>5||x.plan_b_score<1||x.plan_b_score>5))throw new Error(`Ratings must be 1–5 for ${item.case_id}.`);
      const confidence=Number(requireValue(`[name="${item.case_id}::confidence"]`,`Confidence missing for ${item.case_id}.`));
      if(confidence<0||confidence>1)throw new Error(`Confidence must be 0–1 for ${item.case_id}.`);
      reviews.push({
        case_id:item.case_id,assignment_id:item.assignment_id,preference,ratings,confidence,
        observed_at:new Date().toISOString(),algorithm_identity_was_hidden:true,reason_codes:[],activation_authorized:false
      });
    }
    const payload={
      schema:"applaylist-human-dj-review-submission-r1",protocol_version:packet.protocol_version,
      packet_fingerprint:packet.packet_fingerprint,reviewer_ref:reviewer,reviews,
      activation_authorized:false,personal_dj_model_training_authorized:false
    };
    const blob=new Blob([JSON.stringify(payload,null,2)+"\\n"],{type:"application/json"});
    const link=document.createElement("a");link.href=URL.createObjectURL(blob);
    link.download=`applaylist-human-dj-review-${reviewer}.json`;link.click();URL.revokeObjectURL(link.href);
  }catch(error){status.textContent=error instanceof Error?error.message:"Review export failed."}
});
</script>
</body>
</html>
"""
    return (
        template.replace("__TITLE__", html.escape(title))
        .replace("__PACKET__", embedded)
        .encode("utf-8")
    )


def _case_lookup(packet: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    validated = validate_reviewer_packet(packet)
    by_case = {item["case_id"]: item for item in validated["cases"]}
    by_assignment = {item["assignment_id"]: item for item in validated["cases"]}
    return by_case, by_assignment


def _number(value: object, field: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HumanDJReviewExecutionError(f"{field} must be numeric")
    result = float(value)
    if not minimum <= result <= maximum:
        raise HumanDJReviewExecutionError(f"{field} must be between {minimum} and {maximum}")
    return result


def parse_review_submission(
    *,
    packet: Mapping[str, Any],
    submission: Mapping[str, Any],
) -> tuple[str, tuple[tuple[str, HumanDJReview], ...]]:
    validated_packet = validate_reviewer_packet(packet)
    if submission.get("schema") != HUMAN_DJ_REVIEW_SUBMISSION_SCHEMA:
        raise HumanDJReviewExecutionError("unsupported human DJ review submission schema")
    if submission.get("protocol_version") != HUMAN_DJ_REVIEW_PROTOCOL_VERSION:
        raise HumanDJReviewExecutionError("submission protocol version mismatch")
    if submission.get("packet_fingerprint") != validated_packet["packet_fingerprint"]:
        raise HumanDJReviewExecutionError("submission is stale or belongs to another reviewer packet")
    if submission.get("activation_authorized") is not False:
        raise HumanDJReviewExecutionError("human review submission cannot authorize activation")
    if submission.get("personal_dj_model_training_authorized") is not False:
        raise HumanDJReviewExecutionError("human review submission cannot authorize Personal DJ Model training")

    reviewer_ref = _token(submission.get("reviewer_ref"), "reviewer_ref")
    reviews_raw = submission.get("reviews")
    if not isinstance(reviews_raw, list) or not reviews_raw:
        raise HumanDJReviewExecutionError("submission reviews must be a non-empty array")

    by_case, by_assignment = _case_lookup(validated_packet)
    seen_cases: set[str] = set()
    parsed: list[tuple[str, HumanDJReview]] = []
    for raw in reviews_raw:
        if not isinstance(raw, dict):
            raise HumanDJReviewExecutionError("review must be an object")
        allowed_keys = {
            "case_id",
            "assignment_id",
            "preference",
            "ratings",
            "confidence",
            "observed_at",
            "algorithm_identity_was_hidden",
            "reason_codes",
            "activation_authorized",
        }
        if set(raw) != allowed_keys:
            raise HumanDJReviewExecutionError("review has unexpected fields")
        case_id = _token(raw["case_id"], "case_id")
        assignment_id = _token(raw["assignment_id"], "assignment_id")
        if case_id in seen_cases:
            raise HumanDJReviewExecutionError("submission contains duplicate review for one case")
        seen_cases.add(case_id)
        case = by_case.get(case_id)
        assignment_case = by_assignment.get(assignment_id)
        if case is None or assignment_case is None or case is not assignment_case:
            raise HumanDJReviewExecutionError("review case/assignment does not match the blinded packet")
        if raw.get("algorithm_identity_was_hidden") is not True:
            raise HumanDJReviewExecutionError("review is invalid when algorithm identity was visible")
        if raw.get("activation_authorized") is not False:
            raise HumanDJReviewExecutionError("review cannot authorize activation")

        try:
            preference = HumanPlanPreference(str(raw["preference"]))
        except ValueError as exc:
            raise HumanDJReviewExecutionError("review preference is invalid") from exc

        ratings_raw = raw["ratings"]
        if not isinstance(ratings_raw, list):
            raise HumanDJReviewExecutionError("review ratings must be an array")
        ratings: list[HumanDimensionPairRating] = []
        dimensions: list[str] = []
        for item in ratings_raw:
            if not isinstance(item, dict) or set(item) != {
                "dimension",
                "plan_a_score",
                "plan_b_score",
            }:
                raise HumanDJReviewExecutionError("review rating has unexpected fields")
            dimension = str(item["dimension"])
            dimensions.append(dimension)
            try:
                dimension_enum = next(
                    value for value in REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1 if value.value == dimension
                )
            except StopIteration as exc:
                raise HumanDJReviewExecutionError("review rating dimension is invalid") from exc
            ratings.append(
                HumanDimensionPairRating(
                    dimension=dimension_enum,
                    plan_a_score=_number(item["plan_a_score"], "plan_a_score", 1.0, 5.0),
                    plan_b_score=_number(item["plan_b_score"], "plan_b_score", 1.0, 5.0),
                )
            )
        if tuple(dimensions) != _REQUIRED_DIMENSIONS:
            raise HumanDJReviewExecutionError("review must contain all six R1 dimensions in canonical order")

        reason_codes_raw = raw["reason_codes"]
        if not isinstance(reason_codes_raw, list):
            raise HumanDJReviewExecutionError("reason_codes must be an array")
        reason_codes = tuple(_token(item, "reason_code") for item in reason_codes_raw)
        observed_at = _token(raw["observed_at"], "observed_at")
        confidence = _number(raw["confidence"], "confidence", 0.0, 1.0)
        review_material = {
            "packet_fingerprint": validated_packet["packet_fingerprint"],
            "case_id": case_id,
            "assignment_id": assignment_id,
            "reviewer_ref": reviewer_ref,
            "preference": preference.value,
            "ratings": [
                {
                    "dimension": rating.dimension.value,
                    "plan_a_score": rating.plan_a_score,
                    "plan_b_score": rating.plan_b_score,
                }
                for rating in ratings
            ],
            "confidence": confidence,
            "observed_at": observed_at,
            "reason_codes": list(reason_codes),
        }
        review_id = "hdr_" + _sha256_bytes(_canonical_json_bytes(review_material))[:32]
        parsed.append(
            (
                case_id,
                HumanDJReview(
                    review_id=review_id,
                    assignment_id=assignment_id,
                    reviewer_ref=reviewer_ref,
                    preference=preference,
                    ratings=tuple(ratings),
                    confidence=confidence,
                    observed_at=observed_at,
                    algorithm_identity_was_hidden=True,
                    reason_codes=reason_codes,
                    evidence_refs=(f"packet:{validated_packet['packet_fingerprint']}",),
                    activation_authorized=False,
                ),
            )
        )
    return reviewer_ref, tuple(parsed)


class HumanDJReviewLedger:
    """Append-only local ledger for real human DJ review evidence."""

    def __init__(self, database_path: str | Path) -> None:
        self._path = Path(database_path).expanduser().resolve()

    def ensure_schema(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS human_dj_reviews (
                    review_id TEXT PRIMARY KEY,
                    packet_fingerprint TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    assignment_id TEXT NOT NULL,
                    reviewer_ref TEXT NOT NULL,
                    review_json TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    activation_authorized INTEGER NOT NULL DEFAULT 0 CHECK (activation_authorized = 0),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (packet_fingerprint, case_id, reviewer_ref)
                );
                CREATE INDEX IF NOT EXISTS idx_human_dj_reviews_packet
                    ON human_dj_reviews(packet_fingerprint, case_id, reviewer_ref);
                CREATE TRIGGER IF NOT EXISTS human_dj_reviews_no_update
                    BEFORE UPDATE ON human_dj_reviews
                    BEGIN SELECT RAISE(ABORT, 'human DJ reviews are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS human_dj_reviews_no_delete
                    BEFORE DELETE ON human_dj_reviews
                    BEGIN SELECT RAISE(ABORT, 'human DJ reviews are immutable'); END;
                """
            )

    @staticmethod
    def _review_payload(review: HumanDJReview) -> dict[str, Any]:
        return {
            "review_id": review.review_id,
            "assignment_id": review.assignment_id,
            "reviewer_ref": review.reviewer_ref,
            "preference": review.preference.value,
            "ratings": [
                {
                    "dimension": item.dimension.value,
                    "plan_a_score": item.plan_a_score,
                    "plan_b_score": item.plan_b_score,
                }
                for item in review.ratings
            ],
            "confidence": review.confidence,
            "observed_at": review.observed_at,
            "algorithm_identity_was_hidden": True,
            "reason_codes": list(review.reason_codes),
            "evidence_refs": list(review.evidence_refs),
            "activation_authorized": False,
        }

    @staticmethod
    def _review_from_payload(raw: Mapping[str, Any]) -> HumanDJReview:
        return HumanDJReview(
            review_id=str(raw["review_id"]),
            assignment_id=str(raw["assignment_id"]),
            reviewer_ref=str(raw["reviewer_ref"]),
            preference=HumanPlanPreference(str(raw["preference"])),
            ratings=tuple(
                HumanDimensionPairRating(
                    dimension=next(
                        item
                        for item in REQUIRED_HUMAN_REVIEW_DIMENSIONS_R1
                        if item.value == str(rating["dimension"])
                    ),
                    plan_a_score=float(rating["plan_a_score"]),
                    plan_b_score=float(rating["plan_b_score"]),
                )
                for rating in raw["ratings"]
            ),
            confidence=float(raw["confidence"]),
            observed_at=str(raw["observed_at"]),
            algorithm_identity_was_hidden=bool(raw["algorithm_identity_was_hidden"]),
            reason_codes=tuple(str(item) for item in raw.get("reason_codes", ())),
            evidence_refs=tuple(str(item) for item in raw.get("evidence_refs", ())),
            activation_authorized=bool(raw["activation_authorized"]),
        )

    def append(
        self,
        *,
        packet_fingerprint: str,
        reviews: Sequence[tuple[str, HumanDJReview]],
    ) -> tuple[str, ...]:
        self.ensure_schema()
        inserted: list[str] = []
        with sqlite3.connect(self._path) as conn:
            for case_id, review in reviews:
                payload = self._review_payload(review)
                canonical = _canonical_json_bytes(payload).decode("utf-8").rstrip("\n")
                existing = conn.execute(
                    """
                    SELECT review_id, review_json FROM human_dj_reviews
                    WHERE packet_fingerprint = ? AND case_id = ? AND reviewer_ref = ?
                    """,
                    (packet_fingerprint, case_id, review.reviewer_ref),
                ).fetchone()
                if existing is not None:
                    if existing[0] == review.review_id and existing[1] == canonical:
                        inserted.append(review.review_id)
                        continue
                    raise HumanDJReviewExecutionError(
                        "a reviewer may submit only one immutable review per curated case"
                    )
                conn.execute(
                    """
                    INSERT INTO human_dj_reviews (
                        review_id, packet_fingerprint, case_id, assignment_id,
                        reviewer_ref, review_json, observed_at, activation_authorized
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        review.review_id,
                        packet_fingerprint,
                        case_id,
                        review.assignment_id,
                        review.reviewer_ref,
                        canonical,
                        review.observed_at,
                    ),
                )
                inserted.append(review.review_id)
            conn.commit()
        return tuple(inserted)

    def list_for_packet(self, packet_fingerprint: str) -> tuple[HumanDJReview, ...]:
        self.ensure_schema()
        with sqlite3.connect(self._path) as conn:
            rows = conn.execute(
                """
                SELECT review_json FROM human_dj_reviews
                WHERE packet_fingerprint = ?
                ORDER BY case_id ASC, reviewer_ref ASC, review_id ASC
                """,
                (packet_fingerprint,),
            ).fetchall()
        return tuple(self._review_from_payload(json.loads(row[0])) for row in rows)


def ingest_review_submission(
    *,
    packet: Mapping[str, Any],
    submission: Mapping[str, Any],
    ledger: HumanDJReviewLedger,
) -> dict[str, Any]:
    validated = validate_reviewer_packet(packet)
    reviewer_ref, reviews = parse_review_submission(packet=validated, submission=submission)
    review_ids = ledger.append(
        packet_fingerprint=validated["packet_fingerprint"],
        reviews=reviews,
    )
    receipt = {
        "schema": "applaylist-human-dj-review-ingest-receipt-r1",
        "protocol_version": HUMAN_DJ_REVIEW_PROTOCOL_VERSION,
        "packet_fingerprint": validated["packet_fingerprint"],
        "reviewer_ref": reviewer_ref,
        "review_count": len(review_ids),
        "review_ids": list(review_ids),
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
    }
    receipt["receipt_fingerprint"] = _sha256_bytes(_canonical_json_bytes(receipt))
    return receipt


def _parse_plan(raw: Mapping[str, Any]) -> ReviewableSetPlan:
    return ReviewableSetPlan(
        plan_id=_token(raw.get("plan_id"), "plan_id"),
        strategy=ReviewPlanStrategy(str(raw.get("strategy"))),
        result_id=_token(raw.get("result_id"), "result_id"),
        path_id=_token(raw.get("path_id"), "path_id"),
        ordered_track_ids=tuple(_token(item, "ordered_track_id") for item in raw.get("ordered_track_ids", ())),
        transition_ids=tuple(_token(item, "transition_id") for item in raw.get("transition_ids", ())),
        evidence_refs=tuple(str(item) for item in raw.get("evidence_refs", ())),
    )


def _trusted_review_inputs(
    *,
    packet: Mapping[str, Any],
    private_manifest: Mapping[str, Any],
) -> tuple[
    CuratedLibrarySnapshot,
    tuple[CuratedReviewCase, ...],
    tuple[BlindedPlanAssignment, ...],
]:
    validated = validate_reviewer_packet(packet)
    if private_manifest.get("schema") != PRIVATE_RUNTIME_EVIDENCE_SCHEMA:
        raise HumanDJReviewExecutionError("unsupported private runtime evidence schema")
    privacy = private_manifest.get("privacy")
    if (
        not isinstance(privacy, Mapping)
        or privacy.get("contains_local_absolute_paths") is not True
        or privacy.get("publishable_to_public_repo") is not False
    ):
        raise HumanDJReviewExecutionError("private runtime evidence privacy contract is invalid")
    if private_manifest.get("activation_authorized") is not False:
        raise HumanDJReviewExecutionError("private runtime evidence cannot authorize activation")
    if private_manifest.get("personal_dj_model_training_authorized") is not False:
        raise HumanDJReviewExecutionError("private runtime evidence cannot authorize Personal DJ Model training")
    snapshot_ref = private_manifest.get("snapshot_ref")
    if snapshot_ref != validated["snapshot_ref"]:
        raise HumanDJReviewExecutionError("private runtime snapshot does not match reviewer packet")
    tracks = private_manifest.get("tracks")
    if not isinstance(tracks, list) or len(tracks) < 2:
        raise HumanDJReviewExecutionError("private runtime tracks are unavailable")
    track_ids = tuple(_token(item.get("track_id"), "track_id") for item in tracks if isinstance(item, Mapping))
    if len(track_ids) != len(tracks) or len(set(track_ids)) != len(track_ids):
        raise HumanDJReviewExecutionError("private runtime track identities are invalid")
    snapshot = CuratedLibrarySnapshot(
        snapshot_id=str(snapshot_ref[0]),
        snapshot_version=str(snapshot_ref[1]),
        library_fingerprint=_token(private_manifest.get("library_fingerprint"), "library_fingerprint", maximum=512),
        track_ids=track_ids,
        generated_at=_token(private_manifest.get("generated_at"), "generated_at"),
        evidence_refs=("private_runtime_manifest",),
    )

    cases_raw = private_manifest.get("cases")
    if not isinstance(cases_raw, list) or not cases_raw:
        raise HumanDJReviewExecutionError("private runtime review cases are unavailable")
    cases: list[CuratedReviewCase] = []
    assignments: list[BlindedPlanAssignment] = []
    private_by_case: dict[str, tuple[CuratedReviewCase, BlindedPlanAssignment]] = {}
    for row in cases_raw:
        if not isinstance(row, Mapping):
            raise HumanDJReviewExecutionError("private runtime case row is invalid")
        case_raw = row.get("case")
        assignment_raw = row.get("assignment")
        if not isinstance(case_raw, Mapping) or not isinstance(assignment_raw, Mapping):
            raise HumanDJReviewExecutionError("private runtime case/assignment is invalid")
        case = CuratedReviewCase(
            case_id=_token(case_raw.get("case_id"), "case_id"),
            snapshot_ref=tuple(str(item) for item in case_raw.get("snapshot_ref", ())),
            scenario_fingerprint=_token(case_raw.get("scenario_fingerprint"), "scenario_fingerprint", maximum=512),
            set_role=CuratedSetRole(str(case_raw.get("set_role"))),
            benchmark_ref=tuple(str(item) for item in case_raw.get("benchmark_ref", ())),
            greedy_plan=_parse_plan(case_raw.get("greedy_plan", {})),
            beam_plan=_parse_plan(case_raw.get("beam_plan", {})),
            engineering_acceptance_passed=bool(case_raw.get("engineering_acceptance_passed")),
            evidence_refs=tuple(str(item) for item in case_raw.get("evidence_refs", ())),
        )
        assignment = BlindedPlanAssignment(
            assignment_id=_token(assignment_raw.get("assignment_id"), "assignment_id"),
            case_id=_token(assignment_raw.get("case_id"), "assignment case_id"),
            slot_a_plan_id=_token(assignment_raw.get("slot_a_plan_id"), "slot_a_plan_id"),
            slot_b_plan_id=_token(assignment_raw.get("slot_b_plan_id"), "slot_b_plan_id"),
            assignment_fingerprint=_token(
                assignment_raw.get("assignment_fingerprint"),
                "assignment_fingerprint",
                maximum=512,
            ),
            algorithm_identity_hidden=bool(assignment_raw.get("algorithm_identity_hidden")),
        )
        if assignment.case_id != case.case_id:
            raise HumanDJReviewExecutionError("private assignment case identity mismatch")
        if case.case_id in private_by_case:
            raise HumanDJReviewExecutionError("private runtime case identities must be unique")
        private_by_case[case.case_id] = (case, assignment)
        cases.append(case)
        assignments.append(assignment)

    packet_cases = {item["case_id"]: item for item in validated["cases"]}
    if set(packet_cases) != set(private_by_case):
        raise HumanDJReviewExecutionError("private runtime cases do not match reviewer packet")
    for case_id, packet_case in packet_cases.items():
        _, assignment = private_by_case[case_id]
        if packet_case["assignment_id"] != assignment.assignment_id:
            raise HumanDJReviewExecutionError("private assignment identity does not match reviewer packet")

    return snapshot, tuple(cases), tuple(assignments)


def aggregate_human_dj_review(
    *,
    packet: Mapping[str, Any],
    private_manifest: Mapping[str, Any],
    ledger: HumanDJReviewLedger,
) -> dict[str, Any]:
    validated = validate_reviewer_packet(packet)
    snapshot, cases, assignments = _trusted_review_inputs(
        packet=validated,
        private_manifest=private_manifest,
    )
    reviews = ledger.list_for_packet(validated["packet_fingerprint"])
    report = evaluate_curated_real_library_human_review_r1(
        snapshot=snapshot,
        cases=cases,
        assignments=assignments,
        reviews=reviews,
    )
    report_payload = asdict(report)
    aggregate = {
        "schema": HUMAN_DJ_REVIEW_AGGREGATE_SCHEMA,
        "protocol_version": HUMAN_DJ_REVIEW_PROTOCOL_VERSION,
        "packet_fingerprint": validated["packet_fingerprint"],
        "report": report_payload,
        "activation_authorized": False,
        "personal_dj_model_training_authorized": False,
        "musical_superiority_implied": False,
    }
    aggregate["aggregate_fingerprint"] = _sha256_bytes(_canonical_json_bytes(aggregate))
    return aggregate


def write_reviewer_workspace(
    *,
    packet_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    packet = _load_json_object(packet_path)
    material = build_reviewer_workspace(packet)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise HumanDJReviewExecutionError("reviewer workspace output already exists")
    target.write_bytes(material)
    return {
        "workspace_name": target.name,
        "workspace_sha256": _sha256_bytes(material),
        "bytes": len(material),
    }


__all__ = [
    "BLIND_REVIEW_PACKET_SCHEMA",
    "HUMAN_DJ_REVIEW_AGGREGATE_SCHEMA",
    "HUMAN_DJ_REVIEW_SUBMISSION_SCHEMA",
    "HumanDJReviewExecutionError",
    "HumanDJReviewLedger",
    "aggregate_human_dj_review",
    "build_reviewer_workspace",
    "ingest_review_submission",
    "parse_review_submission",
    "reviewer_packet_fingerprint",
    "validate_reviewer_packet",
    "write_reviewer_workspace",
]
