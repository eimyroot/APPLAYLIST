from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

from services.intelligence.real_library_incremental_pilot import (
    materialize_real_library_pilot_incremental_r1,
)


def _emit_progress(event: Mapping[str, int | str]) -> None:
    print("MIR_PROGRESS " + json.dumps(dict(event), sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize APPLAYLIST real-library MIR evidence with exact incremental reuse, "
            "TransitionAssessment adjacency, greedy/beam plan pairs, and a blinded Human DJ "
            "Review R1 packet."
        )
    )
    parser.add_argument("--snapshot", required=True, help="Private LOCAL_LIBRARY_SNAPSHOT_R1 JSON")
    parser.add_argument("--cases", required=True, help="Private CURATED_CASE_SELECTION_R1 JSON")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--database", required=True, help="Dedicated per-run transition database path")
    parser.add_argument(
        "--analysis-database",
        help=(
            "Persistent private AnalysisEvidence SQLite path. When omitted, a stable database "
            "beside the run directories is used automatically."
        ),
    )
    parser.add_argument("--generated-at", required=True, help="Stable evidence timestamp/label")
    parser.add_argument("--blinding-seed", required=True, help="Private deterministic blinding seed")
    args = parser.parse_args()

    result = materialize_real_library_pilot_incremental_r1(
        snapshot_path=Path(args.snapshot),
        selection_path=Path(args.cases),
        output_dir=Path(args.output_dir),
        database_path=Path(args.database),
        analysis_database_path=(Path(args.analysis_database) if args.analysis_database else None),
        generated_at=args.generated_at,
        blinding_seed=args.blinding_seed,
        progress=_emit_progress,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
