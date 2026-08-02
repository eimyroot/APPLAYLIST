from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _ensure_repo_root_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


def main() -> int:
    _ensure_repo_root_on_path()
    from data.migrations.sqlite_backup import (
        BackupEvidence,
        SQLiteBackupError,
        verify_disposable_restore,
    )

    parser = argparse.ArgumentParser(description="Verify SQLite backup via disposable restore")
    parser.add_argument("manifest", help="BACKUP_MANIFEST.json path")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        evidence_fields = {
            field: payload[field]
            for field in BackupEvidence.__dataclass_fields__
        }
        evidence = BackupEvidence(**evidence_fields)
        result = verify_disposable_restore(evidence)
    except (KeyError, OSError, ValueError, RuntimeError, SQLiteBackupError) as exc:
        print(f"DB_RESTORE_VERIFY_ERROR={exc}")
        return 20

    print("SQLITE_DISPOSABLE_RESTORE_VERIFY=PASS")
    print(f"RESTORED_USER_VERSION={result.restored_user_version}")
    print(f"RESTORED_SCHEMA_SHA256={result.restored_schema_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
