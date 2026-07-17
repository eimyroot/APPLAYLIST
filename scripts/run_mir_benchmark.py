#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.analysis.benchmark import (  # noqa: E402
    MIRBenchmarkRunner,
    load_dataset_manifest,
    write_benchmark_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the local APPLAYLIST MIR benchmark against an externally "
            "stored, pre-licensed dataset manifest."
        )
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="Absolute manifest JSON path",
    )
    parser.add_argument(
        "--dataset-root",
        required=True,
        help="Absolute root containing manifest-referenced audio files",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Absolute JSON report output path",
    )
    parser.add_argument(
        "--provider",
        default="librosa",
        help="Explicit provider name; defaults to librosa",
    )
    parser.add_argument(
        "--source-commit",
        default=os.getenv("APPLAYLIST_SOURCE_COMMIT") or os.getenv("GITHUB_SHA"),
        help="Source commit recorded in report provenance",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.source_commit:
        raise SystemExit(
            "--source-commit or APPLAYLIST_SOURCE_COMMIT/GITHUB_SHA is required"
        )

    manifest = load_dataset_manifest(
        Path(args.manifest),
        dataset_root=Path(args.dataset_root),
    )
    report = MIRBenchmarkRunner().run(
        manifest,
        preferred_provider=args.provider,
        source_commit=args.source_commit,
    )
    output = write_benchmark_report(report, Path(args.output))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
