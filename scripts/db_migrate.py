from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_repo_root_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


def _resolve_database_path(explicit: str | None) -> Path:
    from core.config.settings import get_settings
    from data.connection import _sqlite_path_from_url

    if explicit:
        path = Path(explicit)
    else:
        path = Path(_sqlite_path_from_url(get_settings().database_url))
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.expanduser().resolve()


def main() -> int:
    _ensure_repo_root_on_path()
    from data.migrations.registry import MIGRATIONS
    from data.migrations.runner import MigrationRunnerError, check_database, migration_plan

    parser = argparse.ArgumentParser(description="APPLAYLIST SQLite migration controls")
    parser.add_argument("command", choices=("check", "plan", "apply"))
    parser.add_argument("--database", help="SQLite database path; defaults to app settings")
    args = parser.parse_args()

    db_path = _resolve_database_path(args.database)

    try:
        if args.command == "check":
            result = check_database(db_path, require_legacy_v0=True)
            print(f"DATABASE_PATH={result.path}")
            print(f"PRAGMA_USER_VERSION={result.fingerprint.user_version}")
            print(f"SCHEMA_SHA256={result.fingerprint.sha256}")
            print("LEGACY_V0_SCHEMA_FINGERPRINT=VERIFIED")
            return 0

        if args.command == "plan":
            plan = migration_plan(db_path, MIGRATIONS)
            if not plan:
                print("MIGRATION_PLAN=NONE")
                return 0
            for migration in plan:
                print(
                    "MIGRATION_PLAN_STEP="
                    f"{migration.from_version}->{migration.to_version}:{migration.name}"
                )
            return 0

        print("MIGRATION_APPLY=BLOCKED_NO_REGISTERED_MIGRATION")
        return 20
    except (MigrationRunnerError, RuntimeError, FileNotFoundError) as exc:
        print(f"MIGRATION_CONTROL_ERROR={exc}")
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
