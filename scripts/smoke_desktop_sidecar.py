from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PROTOCOL = "applaylist-sidecar-v1"
SECRET = "package-smoke-secret-0123456789-ABCDEFGH"
NONCE = "package-smoke-nonce-0123456789-IJKLMNOP"


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test a packaged APPLAYLIST sidecar")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    repository_root = Path(__file__).resolve().parents[1]
    manifest_path = args.manifest.resolve(strict=True)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    executable = (repository_root / payload["executable"]).resolve(strict=True)
    if repository_root not in executable.parents:
        raise SystemExit("packaged executable escaped repository root")

    process = subprocess.Popen(
        [str(executable)],
        cwd=repository_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(
        json.dumps(
            {"protocol": PROTOCOL, "secret": SECRET, "nonce": NONCE},
            separators=(",", ":"),
        )
        + "\n"
    )
    process.stdin.flush()
    ready_line = process.stdout.readline()
    if not ready_line:
        stderr = process.stderr.read() if process.stderr is not None else ""
        process.kill()
        raise SystemExit(f"packaged sidecar did not become ready: {stderr}")
    ready = json.loads(ready_line)
    expected_nonce_digest = hashlib.sha256(NONCE.encode("ascii")).hexdigest()
    if ready.get("host") != "127.0.0.1" or ready.get("nonce_sha256") != expected_nonce_digest:
        process.kill()
        raise SystemExit("packaged sidecar readiness evidence is invalid")

    base_url = f"http://127.0.0.1:{ready['port']}"
    wrong = Request(
        base_url + "/v1/health",
        headers={
            "X-APPLAYLIST-Sidecar-Secret": "X" * 48,
            "X-APPLAYLIST-Readiness-Nonce": NONCE,
        },
    )
    try:
        urlopen(wrong, timeout=5)  # noqa: S310 - fixed loopback target
        process.kill()
        raise SystemExit("packaged sidecar accepted an invalid secret")
    except HTTPError as exc:
        if exc.code != 401:
            process.kill()
            raise

    health = Request(
        base_url + "/v1/health",
        headers={
            "X-APPLAYLIST-Sidecar-Secret": SECRET,
            "X-APPLAYLIST-Readiness-Nonce": NONCE,
        },
    )
    with urlopen(health, timeout=5) as response:  # noqa: S310 - fixed loopback target
        health_payload = json.loads(response.read().decode("utf-8"))
    if health_payload.get("status") != "ready":
        process.kill()
        raise SystemExit("packaged sidecar health response is invalid")

    shutdown = Request(
        base_url + "/v1/shutdown",
        method="POST",
        data=b"",
        headers={
            "X-APPLAYLIST-Sidecar-Secret": SECRET,
            "X-APPLAYLIST-Readiness-Nonce": NONCE,
        },
    )
    with urlopen(shutdown, timeout=5) as response:  # noqa: S310 - fixed loopback target
        if response.status != 202:
            process.kill()
            raise SystemExit("packaged sidecar shutdown was rejected")

    stdout, stderr = process.communicate(timeout=10)
    if process.returncode != 0:
        raise SystemExit(f"packaged sidecar exited with {process.returncode}: {stderr}")
    combined = ready_line + stdout + stderr
    if SECRET in combined or NONCE in combined:
        raise SystemExit("packaged sidecar disclosed private startup credentials")

    print(
        json.dumps(
            {
                "status": "passed",
                "executable": str(executable),
                "package_size_bytes": payload["size_bytes"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
