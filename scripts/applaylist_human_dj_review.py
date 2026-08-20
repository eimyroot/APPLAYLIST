from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.intelligence.human_dj_review_execution import (
    HumanDJReviewLedger,
    aggregate_human_dj_review,
    ingest_review_submission,
    validate_reviewer_packet,
    write_reviewer_workspace,
)


def _load(path: str) -> dict[str, object]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SystemExit(f"JSON object required: {path}")
    return raw


def _write_json(path: str, payload: object) -> None:
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
        description="Governed APPLAYLIST blinded Human DJ Review R1 execution tooling."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    workspace = sub.add_parser(
        "workspace",
        help="Generate a self-contained blinded reviewer HTML workspace.",
    )
    workspace.add_argument("--packet", required=True)
    workspace.add_argument("--output", required=True)

    ingest = sub.add_parser(
        "ingest",
        help="Validate and append a real human review submission.",
    )
    ingest.add_argument("--packet", required=True)
    ingest.add_argument("--submission", required=True)
    ingest.add_argument("--ledger", required=True)
    ingest.add_argument("--receipt", required=True)

    report = sub.add_parser(
        "report",
        help="Aggregate append-only human review evidence using the trusted private runtime manifest.",
    )
    report.add_argument("--packet", required=True)
    report.add_argument("--private-manifest", required=True)
    report.add_argument("--ledger", required=True)
    report.add_argument("--output", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "workspace":
        result = write_reviewer_workspace(packet_path=args.packet, output_path=args.output)
        print(json.dumps(result, sort_keys=True))
        return 0

    packet = _load(args.packet)
    validate_reviewer_packet(packet)
    ledger = HumanDJReviewLedger(args.ledger)

    if args.command == "ingest":
        submission = _load(args.submission)
        receipt = ingest_review_submission(
            packet=packet,
            submission=submission,
            ledger=ledger,
        )
        _write_json(args.receipt, receipt)
        print(
            json.dumps(
                {
                    "receipt": Path(args.receipt).name,
                    "review_count": receipt["review_count"],
                },
                sort_keys=True,
            )
        )
        return 0

    if args.command == "report":
        private_manifest = _load(args.private_manifest)
        aggregate = aggregate_human_dj_review(
            packet=packet,
            private_manifest=private_manifest,
            ledger=ledger,
        )
        _write_json(args.output, aggregate)
        report = aggregate["report"]
        verdict = report["verdict"] if isinstance(report, dict) else "unknown"
        print(
            json.dumps(
                {"report": Path(args.output).name, "verdict": str(verdict)},
                sort_keys=True,
            )
        )
        return 0

    raise SystemExit("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
