from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.intelligence.fresh_personal_holdout_runner import (
    materialize_fresh_personal_holdout_r1,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize a fresh blinded personal curation holdout locally."
    )
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--canonical-sha", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--sampling-seed", required=True)
    parser.add_argument("--blinding-seed", required=True)
    parser.add_argument("--cases-per-role", type=int, default=8)
    parser.add_argument("--candidate-scope-size", type=int, default=16)
    parser.add_argument("--fallback-count", type=int, default=12)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = materialize_fresh_personal_holdout_r1(
        snapshot_path=Path(args.snapshot),
        output_dir=Path(args.output),
        database_path=Path(args.database),
        canonical_sha=args.canonical_sha,
        generated_at=args.generated_at,
        sampling_seed=args.sampling_seed,
        blinding_seed=args.blinding_seed,
        cases_per_role=args.cases_per_role,
        candidate_scope_size=args.candidate_scope_size,
        fallback_count=args.fallback_count,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
