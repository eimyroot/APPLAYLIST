from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.intelligence.r4_pilot_evidence import (
    PilotEvidenceLedger,
    build_r4_pilot_report,
)


def _load(path: str) -> dict[str, object]:
    source = Path(path)
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SystemExit(f"JSON object required: {source}")
    return raw


def _write(path: str, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise SystemExit(f"output already exists: {target}")
    target.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local-first APPLAYLIST R4 bounded DJ pilot evidence tooling."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    event = sub.add_parser("event", help="Validate and append one real pilot workflow event.")
    event.add_argument("--ledger", required=True)
    event.add_argument("--input", required=True)
    event.add_argument("--receipt", required=True)

    survey = sub.add_parser("survey", help="Validate and append one explicit pilot survey.")
    survey.add_argument("--ledger", required=True)
    survey.add_argument("--input", required=True)
    survey.add_argument("--receipt", required=True)

    report = sub.add_parser("report", help="Aggregate local pilot evidence deterministically.")
    report.add_argument("--ledger", required=True)
    report.add_argument("--output", required=True)
    report.add_argument("--human-review-aggregate")
    return parser


def main() -> int:
    args = _parser().parse_args()
    ledger = PilotEvidenceLedger(args.ledger)

    if args.command == "event":
        receipt = ledger.record_event(_load(args.input))
        _write(args.receipt, receipt)
        print(json.dumps({"kind": "event", "record_id": receipt["record_id"]}, sort_keys=True))
        return 0

    if args.command == "survey":
        receipt = ledger.record_survey(_load(args.input))
        _write(args.receipt, receipt)
        print(json.dumps({"kind": "survey", "record_id": receipt["record_id"]}, sort_keys=True))
        return 0

    if args.command == "report":
        human_review = (
            _load(args.human_review_aggregate) if args.human_review_aggregate else None
        )
        report = build_r4_pilot_report(
            ledger=ledger,
            human_review_aggregate=human_review,
        )
        _write(args.output, report)
        print(
            json.dumps(
                {
                    "evidence_state": report["evidence_state"],
                    "product_decision": report["product_decision"],
                    "report": Path(args.output).name,
                },
                sort_keys=True,
            )
        )
        return 0

    raise SystemExit("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
