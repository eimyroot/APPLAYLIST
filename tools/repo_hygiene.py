from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from tools.repo_hygiene_core import (
    HygieneError,
    audit_repository,
    quarantine_report,
    report_markdown,
    resolve_repo_root,
    restore_manifest,
    write_report,
)
from tools.repo_hygiene_verify import run_verification


def _add_scope_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--include-generated",
        action="store_true",
        help="allow runtime-generated artifacts, exports, logs and tmp directories",
    )
    parser.add_argument(
        "--include-heavy",
        action="store_true",
        help="allow virtualenv, node_modules and frontend build directories",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit and safely quarantine local APPLAYLIST repository clutter.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="path inside the target Git repository (default: current directory)",
    )
    subparsers = parser.add_subparsers(dest="command")

    audit = subparsers.add_parser("audit", help="write JSON and Markdown audit reports")
    _add_scope_flags(audit)
    audit.add_argument(
        "--stdout",
        action="store_true",
        help="also print the Markdown report",
    )

    quarantine = subparsers.add_parser(
        "quarantine",
        help="show or apply safe quarantine actions",
    )
    _add_scope_flags(quarantine)
    quarantine.add_argument(
        "--apply",
        action="store_true",
        help="perform moves; without this flag the command is a dry-run",
    )

    restore = subparsers.add_parser(
        "restore",
        help="show or restore one quarantine manifest",
    )
    restore.add_argument("manifest", help="manifest path under the repository root")
    restore.add_argument(
        "--apply",
        action="store_true",
        help="perform restoration; without this flag the command is a dry-run",
    )

    verify = subparsers.add_parser(
        "verify",
        help="run Git, syntax and import safety checks without writing bytecode",
    )
    verify.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used for syntax/import checks",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "audit"

    try:
        root = resolve_repo_root(args.root)
        if command == "audit":
            report = audit_repository(
                root,
                include_generated=args.include_generated,
                include_heavy=args.include_heavy,
            )
            json_path, markdown_path = write_report(root, report, label="audit")
            print(f"JSON_REPORT={json_path}")
            print(f"MARKDOWN_REPORT={markdown_path}")
            print(json.dumps(report.summary(), sort_keys=True))
            if args.stdout:
                print()
                print(report_markdown(report))
            return 0

        if command == "quarantine":
            report = audit_repository(
                root,
                include_generated=args.include_generated,
                include_heavy=args.include_heavy,
            )
            json_path, markdown_path = write_report(root, report, label="quarantine-plan")
            manifest_path, count = quarantine_report(root, report, apply=args.apply)
            print(f"JSON_REPORT={json_path}")
            print(f"MARKDOWN_REPORT={markdown_path}")
            print(f"ELIGIBLE_COUNT={count}")
            print(f"APPLIED={'yes' if args.apply else 'no'}")
            if manifest_path is not None:
                print(f"MANIFEST={manifest_path}")
            return 0

        if command == "restore":
            manifest = Path(args.manifest)
            if not manifest.is_absolute():
                manifest = root / manifest
            count = restore_manifest(root, manifest, apply=args.apply)
            print(f"RESTORE_COUNT={count}")
            print(f"APPLIED={'yes' if args.apply else 'no'}")
            return 0

        if command == "verify":
            result = run_verification(root, python_executable=args.python)
            report_dir = root / ".repo-hygiene" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / "latest-verify.json"
            report_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print(f"VERIFY_REPORT={report_path}")
            return 0 if result["success"] else 1

        parser.error(f"unsupported command: {command}")
    except (HygieneError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
