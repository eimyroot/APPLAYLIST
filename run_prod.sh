#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export PYTHONUNBUFFERED=1
export APP_ENV="${APP_ENV:-production}"
export ENABLE_SECURITY_HEADERS="${ENABLE_SECURITY_HEADERS:-true}"
export ENABLE_REQUEST_SIZE_GUARD="${ENABLE_REQUEST_SIZE_GUARD:-true}"
export ENABLE_RATE_LIMIT="${ENABLE_RATE_LIMIT:-true}"
export RATE_LIMIT_PER_MINUTE="${RATE_LIMIT_PER_MINUTE:-120}"
export MAX_REQUEST_BYTES="${MAX_REQUEST_BYTES:-2097152}"

echo "=== APPLAYLIST PROD START ==="
echo "APP_ENV=$APP_ENV"
echo "RATE_LIMIT_PER_MINUTE=$RATE_LIMIT_PER_MINUTE"
echo "MAX_REQUEST_BYTES=$MAX_REQUEST_BYTES"

exec uvicorn api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 2 \
  --proxy-headers \
  --timeout-keep-alive 30
