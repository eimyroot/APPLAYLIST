#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

cp api/main.py "api/main.py.bak.$(date +%Y%m%d_%H%M%S)" || true

cat > api/main.py << 'PYEOF'
from __future__ import annotations

from fastapi import FastAPI

from api.routes.health import router as health_router
from api.routes.jobs import router as jobs_router
from api.routes.pipeline import router as pipeline_router
from api.security.bootstrap import apply_security_hardening

app = FastAPI(
    title="APPLAYLIST API",
    version="0.11.1",
)

apply_security_hardening(app)

app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(pipeline_router)
PYEOF

echo "api/main.py restored with routers + security hardening"
