#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

cp api/main.py "api/main.py.bak.$(date +%Y%m%d_%H%M%S)" || true

cat > api/main.py << 'PYEOF'
from __future__ import annotations

from fastapi import FastAPI

from api.security.bootstrap import apply_security_hardening

app = FastAPI(
    title="APPLAYLIST API",
    version="0.11.0",
)

apply_security_hardening(app)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app": "APPLAYLIST",
        "version": "0.11.0",
    }
PYEOF

echo "api/main.py repaired"
