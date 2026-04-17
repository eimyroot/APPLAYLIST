import os
import time
from fastapi import Request, HTTPException
from collections import defaultdict

RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() == "true"
API_KEY = os.getenv("API_KEY", "")

requests_store = defaultdict(list)

def check_rate_limit(client_ip: str):
    now = time.time()
    window = 60

    requests_store[client_ip] = [
        t for t in requests_store[client_ip] if now - t < window
    ]

    if len(requests_store[client_ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    requests_store[client_ip].append(now)


def check_auth(request: Request):
    if not ENABLE_AUTH:
        return

    key = request.headers.get("x-api-key")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def enforce_size_limit(request: Request):
    max_mb = int(os.getenv("MAX_REQUEST_SIZE_MB", "5"))
    content_length = request.headers.get("content-length")

    if content_length and int(content_length) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Payload too large")
