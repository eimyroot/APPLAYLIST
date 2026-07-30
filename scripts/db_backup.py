from __future__ import annotations

import argparse
import subprocess
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

    raw = explicit if explicit else _sqlite_path_from_url(get_settings().database_url)
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.expanduser().resolve()


def _repository_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def main() -> int:
    _ensure_repo_root_on_path()
    from data.migrations.sqlite_backup import (
        SQLiteBackupError,
        create_verified_backup,
        write_backup_manifest,
    )

    parser = argparse.ArgumentParser(description="Create a verified SQLite backup")
    parser.add_argument("--destination-dir", required=True)
    parser.add_argument("--database", help="SQLite database path; defaults to app settings")
    args = parser.parse_args()

    source = _resolve_database_path(args.database)
    destination_dir = Path(args.destination_dir).expanduser().resolve()
    if not destination_dir.is_dir():
        print(f"DB_BACKUP_ERROR=destination directory missing: {destination_dir}")
        return 20

    backup_path = destination_dir / "applaylist.pre-migration.sqlite3"
    manifest_path = destination_dir / "BACKUP_MANIFEST.json"
    try:
        evidence = create_verified_backup(source, backup_path)
        write_backup_manifest(
            evidence,
            manifest_path,
            repository_head=_repository_head(),
            migration_from_version=None,
            migration_to_version=None,
        )
    except (
        SQLiteBackupError,
        RuntimeError,
        FileNotFoundError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"DB_BACKUP_ERROR={exc}")
        return 20

    print("SQLITE_BACKUP_VERIFY=PASS")
    print(f"BACKUP_PATH={evidence.backup_path}")
    print(f"BACKUP_SHA256={evidence.backup_sha256}")
    print(f"BACKUP_MANIFEST={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
