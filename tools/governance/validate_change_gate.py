#!/usr/bin/env python3
"""Validate APPLAYLIST 7Q change-gate documents using only Python stdlib.

Exit codes:
  0 - truthful VERIFIED_10_OF_10
  3 - truthful PARTIALLY_VERIFIED
  1 - BLOCKED or contradictory claim
  2 - structurally invalid input/schema
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DIMENSIONS = (
    "simple", "purposeful", "automated", "secure",
    "measurable", "reversible", "provable",
)
TRUTH = {"VERIFIED", "IMPLEMENTED", "PROPOSED", "INFERRED", "UNKNOWN", "BLOCKED"}
LIFECYCLE = {
    "DISCOVERED", "INVESTIGATING", "SHAPED", "PROPOSED", "ACCEPTED",
    "PLANNED", "IMPLEMENTING", "IMPLEMENTED", "VERIFIED", "RELEASED",
    "VALIDATED", "DEPRECATED", "RETIRED",
}
RISK = {"T0", "T1", "T2", "T3"}
CONTEXT = {"CLEAR", "COMPLICATED", "COMPLEX", "CHAOTIC", "CONFUSED"}
DIM_STATUS = {"VERIFIED_PASS", "FAILED", "UNKNOWN", "NOT_APPLICABLE_APPROVED"}
GATE = {"VERIFIED_10_OF_10", "PARTIALLY_VERIFIED", "BLOCKED"}
ROOT_REQUIRED = {
    "schema_version", "change_id", "title", "truth_status", "lifecycle_status",
    "risk_tier", "context_domain", "quality_dimensions", "gate_result",
    "remaining_unknowns",
}
ROOT_OPTIONAL = {
    "decision_reference", "work_block_reference", "source_revision", "artifact_digests",
}
DIM_REQUIRED = {"target", "status", "score", "evidence"}
DIM_OPTIONAL = {"rationale", "approved_by"}
HEX64 = re.compile(r"^[a-f0-9]{64}$")
CHANGE_ID = re.compile(r"^[A-Z]+-[0-9A-Z-]+$")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def string_list(value: Any, field: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{field}: expected array")
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field}[{index}]: expected non-empty string")
        else:
            result.append(item)
    if len(result) != len(set(result)):
        errors.append(f"{field}: duplicate values are forbidden")
    return result


def validate_structure(document: Any, schema: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(schema, dict):
        return ["schema: expected object"]
    expected_version = (((schema.get("properties") or {}).get("schema_version") or {}).get("const"))
    if expected_version != "1.0.0":
        errors.append("schema: unsupported or missing schema_version const")
    if not isinstance(document, dict):
        return errors + ["document: expected object"]

    keys = set(document)
    missing = sorted(ROOT_REQUIRED - keys)
    extra = sorted(keys - ROOT_REQUIRED - ROOT_OPTIONAL)
    if missing:
        errors.append(f"document: missing keys: {', '.join(missing)}")
    if extra:
        errors.append(f"document: unexpected keys: {', '.join(extra)}")
    if errors:
        return errors

    if document["schema_version"] != "1.0.0":
        errors.append("schema_version: expected 1.0.0")
    if not isinstance(document["change_id"], str) or not CHANGE_ID.fullmatch(document["change_id"]):
        errors.append("change_id: invalid format")
    if not isinstance(document["title"], str) or len(document["title"].strip()) < 3:
        errors.append("title: expected at least 3 characters")
    for field, allowed in (
        ("truth_status", TRUTH), ("lifecycle_status", LIFECYCLE),
        ("risk_tier", RISK), ("context_domain", CONTEXT), ("gate_result", GATE),
    ):
        if document[field] not in allowed:
            errors.append(f"{field}: unsupported value {document[field]!r}")

    quality = document["quality_dimensions"]
    if not isinstance(quality, dict):
        errors.append("quality_dimensions: expected object")
    else:
        qkeys = set(quality)
        if qkeys != set(DIMENSIONS):
            errors.append("quality_dimensions: must contain exactly seven canonical dimensions")
        for name in DIMENSIONS:
            value = quality.get(name)
            if not isinstance(value, dict):
                errors.append(f"{name}: expected object")
                continue
            keys = set(value)
            missing = DIM_REQUIRED - keys
            extra = keys - DIM_REQUIRED - DIM_OPTIONAL
            if missing:
                errors.append(f"{name}: missing keys: {', '.join(sorted(missing))}")
            if extra:
                errors.append(f"{name}: unexpected keys: {', '.join(sorted(extra))}")
            if missing:
                continue
            if value["target"] != 10:
                errors.append(f"{name}.target: expected 10")
            status = value["status"]
            if status not in DIM_STATUS:
                errors.append(f"{name}.status: unsupported value {status!r}")
            score = value["score"]
            if score is not None and (isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 10):
                errors.append(f"{name}.score: expected integer 0..10 or null")
            evidence = string_list(value["evidence"], f"{name}.evidence", errors)
            if status == "VERIFIED_PASS":
                if score != 10:
                    errors.append(f"{name}: VERIFIED_PASS requires score 10")
                if not evidence:
                    errors.append(f"{name}: VERIFIED_PASS requires evidence")
            elif status == "NOT_APPLICABLE_APPROVED":
                if score is not None:
                    errors.append(f"{name}: NOT_APPLICABLE_APPROVED requires null score")
                if not isinstance(value.get("rationale"), str) or len(value["rationale"].strip()) < 8:
                    errors.append(f"{name}: approved N/A requires substantive rationale")
                if not isinstance(value.get("approved_by"), str) or len(value["approved_by"].strip()) < 2:
                    errors.append(f"{name}: approved N/A requires approved_by")
            elif score == 10:
                errors.append(f"{name}: {status} may not claim score 10")

    string_list(document["remaining_unknowns"], "remaining_unknowns", errors)

    for field in ("decision_reference", "work_block_reference", "source_revision"):
        if field in document and not isinstance(document[field], str):
            errors.append(f"{field}: expected string")

    digests = document.get("artifact_digests", [])
    if not isinstance(digests, list):
        errors.append("artifact_digests: expected array")
    else:
        for index, item in enumerate(digests):
            prefix = f"artifact_digests[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix}: expected object")
                continue
            if set(item) != {"subject", "algorithm", "digest"}:
                errors.append(f"{prefix}: expected subject, algorithm, digest only")
                continue
            if not isinstance(item["subject"], str) or not item["subject"].strip():
                errors.append(f"{prefix}.subject: expected non-empty string")
            if item["algorithm"] != "sha256":
                errors.append(f"{prefix}.algorithm: expected sha256")
            if not isinstance(item["digest"], str) or not HEX64.fullmatch(item["digest"]):
                errors.append(f"{prefix}.digest: expected 64 lowercase hex characters")
    return errors


def compute_result(document: dict[str, Any]) -> tuple[str, list[str]]:
    findings: list[str] = []
    relevant: list[str] = []
    failed: list[str] = []
    unknown: list[str] = []

    for name in DIMENSIONS:
        dimension = document["quality_dimensions"][name]
        status = dimension["status"]
        if status == "NOT_APPLICABLE_APPROVED":
            findings.append(f"{name}: approved not applicable")
            continue
        relevant.append(name)
        if status == "FAILED":
            failed.append(name)
        elif status == "UNKNOWN":
            unknown.append(name)
        elif status != "VERIFIED_PASS" or dimension["score"] != 10 or not dimension["evidence"]:
            failed.append(name)

    remaining = document["remaining_unknowns"]
    if failed or document["truth_status"] == "BLOCKED":
        computed = "BLOCKED"
    elif unknown or remaining:
        computed = "PARTIALLY_VERIFIED"
    else:
        computed = "VERIFIED_10_OF_10"

    if not relevant:
        computed = "BLOCKED"
        findings.append("at least one relevant dimension is required")
    if document["lifecycle_status"] in {"RELEASED", "VALIDATED"} and computed != "VERIFIED_10_OF_10":
        computed = "BLOCKED"
        findings.append("RELEASED/VALIDATED requires a fully verified gate")
    if computed == "VERIFIED_10_OF_10" and document["truth_status"] != "VERIFIED":
        computed = "BLOCKED"
        findings.append("VERIFIED_10_OF_10 requires truth_status=VERIFIED")

    if failed:
        findings.append("failed dimensions: " + ", ".join(failed))
    if unknown:
        findings.append("unknown dimensions: " + ", ".join(unknown))
    if remaining:
        findings.append("remaining unknowns are present")
    return computed, findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("document", type=Path)
    parser.add_argument("--schema", type=Path, default=Path(__file__).with_name("CHANGE_GATE.schema.json"))
    args = parser.parse_args()
    try:
        schema = load_json(args.schema)
        document = load_json(args.document)
    except ValueError as exc:
        print(json.dumps({"status": "BLOCKED", "errors": [str(exc)]}, indent=2))
        return 2

    errors = validate_structure(document, schema)
    if errors:
        print(json.dumps({"status": "BLOCKED", "errors": errors}, indent=2))
        return 2

    computed, findings = compute_result(document)
    declared = document["gate_result"]
    if declared != computed:
        print(json.dumps({
            "status": "BLOCKED",
            "declared_result": declared,
            "computed_result": computed,
            "errors": ["declared gate_result contradicts evidence"],
            "findings": findings,
        }, indent=2))
        return 1

    print(json.dumps({
        "status": computed,
        "change_id": document["change_id"],
        "dimensions": list(DIMENSIONS),
        "remaining_unknowns": document["remaining_unknowns"],
        "findings": findings,
    }, indent=2))
    return 0 if computed == "VERIFIED_10_OF_10" else (3 if computed == "PARTIALLY_VERIFIED" else 1)


if __name__ == "__main__":
    sys.exit(main())
