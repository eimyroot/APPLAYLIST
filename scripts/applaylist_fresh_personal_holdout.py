from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from services.intelligence.fresh_holdout_reviewer_workspace import (
    finalize_fresh_holdout_reviewer_workspace,
)
from services.intelligence.fresh_personal_holdout_runner import (
    FreshPersonalHoldoutRunnerError,
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
    parser.add_argument("--canonical-branch", default="feature/bundle-0-bootstrap")
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--sampling-seed", required=True)
    parser.add_argument("--blinding-seed", required=True)
    parser.add_argument("--cases-per-role", type=int, default=8)
    parser.add_argument("--candidate-scope-size", type=int, default=16)
    parser.add_argument("--fallback-count", type=int, default=12)
    return parser


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def verify_canonical_checkout(*, canonical_sha: str, canonical_branch: str) -> None:
    """Fail closed unless the run is launched from the exact clean canonical checkout."""
    try:
        head = _git("rev-parse", "HEAD")
        branch = _git("rev-parse", "--abbrev-ref", "HEAD")
        dirty = _git("status", "--porcelain")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise FreshPersonalHoldoutRunnerError(
            "fresh holdout run requires a readable local Git checkout"
        ) from exc

    expected_sha = str(canonical_sha).strip()
    expected_branch = str(canonical_branch).strip()
    if not expected_sha or not expected_branch:
        raise FreshPersonalHoldoutRunnerError("canonical SHA/branch must not be empty")
    if head != expected_sha:
        raise FreshPersonalHoldoutRunnerError(
            f"local HEAD {head} does not match declared canonical SHA {expected_sha}"
        )
    if branch != expected_branch:
        raise FreshPersonalHoldoutRunnerError(
            f"local branch {branch} does not match canonical branch {expected_branch}"
        )
    if dirty:
        raise FreshPersonalHoldoutRunnerError(
            "fresh holdout run requires a clean working tree before evidence generation"
        )


def main() -> int:
    args = _parser().parse_args()
    verify_canonical_checkout(
        canonical_sha=args.canonical_sha,
        canonical_branch=args.canonical_branch,
    )
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
    result = finalize_fresh_holdout_reviewer_workspace(result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
