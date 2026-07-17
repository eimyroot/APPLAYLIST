from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


SIDECAR_NAME = "applaylist-sidecar"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the APPLAYLIST Python readiness sidecar")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("artifacts/desktop-sidecar"),
        help="Build output root relative to the repository or as an absolute path",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repository_root = Path(__file__).resolve().parents[1]
    output_root = args.output_root
    if not output_root.is_absolute():
        output_root = (repository_root / output_root).resolve()
    else:
        output_root = output_root.resolve()

    if repository_root not in output_root.parents:
        raise SystemExit("output root must remain inside the repository")

    dist = output_root / "dist"
    work = output_root / "work"
    specs = output_root / "spec"
    if output_root.exists():
        shutil.rmtree(output_root)
    dist.mkdir(parents=True)
    work.mkdir(parents=True)
    specs.mkdir(parents=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        SIDECAR_NAME,
        "--distpath",
        str(dist),
        "--workpath",
        str(work),
        "--specpath",
        str(specs),
        str(repository_root / "scripts" / "applaylist_sidecar_entry.py"),
    ]
    completed = subprocess.run(command, cwd=repository_root, check=False)
    if completed.returncode != 0:
        return completed.returncode

    executable = dist / SIDECAR_NAME / SIDECAR_NAME
    if sys.platform == "win32":
        executable = executable.with_suffix(".exe")
    if not executable.is_file():
        raise SystemExit(f"sidecar executable missing: {executable}")

    manifest = {
        "schema_version": "applaylist-sidecar-package-v1",
        "mode": "onedir",
        "executable": str(executable.relative_to(repository_root)),
        "size_bytes": sum(
            path.stat().st_size for path in (dist / SIDECAR_NAME).rglob("*") if path.is_file()
        ),
        "python": sys.version.split()[0],
        "platform": sys.platform,
    }
    manifest_path = output_root / "package-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
