from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

from tools.repo_hygiene_core import audit_repository


def _run(
    command: list[str],
    *,
    root: Path,
    env: dict[str, str] | None = None,
) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
    )
    return {
        "command": command,
        "success": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def run_verification(root: Path, *, python_executable: str) -> dict[str, object]:
    root = root.resolve(strict=True)
    audit = audit_repository(root)
    tracked_quarantine = [
        candidate.path
        for candidate in audit.candidates
        if candidate.tracked and candidate.proposed_action == "quarantine"
    ]

    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPYCACHEPREFIX"] = str(root / ".repo-hygiene" / "verify-pycache")

    syntax_script = (
        "from pathlib import Path; "
        "import subprocess; "
        "root=Path('.').resolve(); "
        "paths=subprocess.check_output(['git','ls-files','*.py'], text=True).splitlines(); "
        "[(lambda p: compile(p.read_text(encoding='utf-8'), str(p), 'exec'))(root / item) "
        "for item in paths]"
    )

    checks = [
        {
            "name": "git_diff_check",
            **_run(["git", "diff", "--check"], root=root, env=environment),
        },
        {
            "name": "tracked_python_syntax",
            **_run(
                [python_executable, "-B", "-c", syntax_script],
                root=root,
                env=environment,
            ),
        },
        {
            "name": "imports",
            **_run(
                [
                    python_executable,
                    "-B",
                    "-c",
                    "import core, data, services, tools",
                ],
                root=root,
                env=environment,
            ),
        },
    ]

    status = subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    return {
        "repo_root": str(root),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_status": status,
        "tracked_quarantine_violation": tracked_quarantine,
        "audit_summary": audit.summary(),
        "checks": checks,
        "success": not tracked_quarantine and all(check["success"] for check in checks),
    }
