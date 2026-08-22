from __future__ import annotations

import argparse
import json
import sys

from services.intelligence.historical_meaningful_replay import (
    replay_historical_meaningful_review_r1,
)
from services.intelligence.real_library_pilot import RealLibraryPilotError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay Bundle 65 meaningful-diversity/style-energy gates over existing "
            "private real-library evidence without reading or re-analyzing audio."
        )
    )
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--private-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--generated-at", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = replay_historical_meaningful_review_r1(
            snapshot_path=args.snapshot,
            selection_path=args.selection,
            private_manifest_path=args.private_manifest,
            output_path=args.output,
            generated_at=args.generated_at,
        )
    except RealLibraryPilotError as exc:
        print(f"HISTORICAL_MEANINGFUL_REPLAY=FAIL\nERROR={exc}", file=sys.stderr)
        return 2
    print("HISTORICAL_MEANINGFUL_REPLAY=PASS")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
