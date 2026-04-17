from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

_RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))
_ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() == "true"
_API_KEY = os.getenv("API_KEY", "")
_MAX_REQUEST_SIZE_MB = int(os.getenv("MAX_REQUEST_SIZE_MB", "5"))

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()

def check_rate_limit(client_ip: str) -> None:
    now = time.time()
    window = 60.0
    with _lock:
        q = _hits[client_ip]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= _RATE_LIMIT:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        q.append(now)

def check_auth(request: Request) -> None:
    if not _ENABLE_AUTH:
        return
    given = request.headers.get("x-api-key", "")
    if not _API_KEY or given != _API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

def check_payload_size(request: Request) -> None:
    cl = request.headers.get("content-length")
    if not cl:
        return
    try:
        size = int(cl)
    except ValueError:
        return
    if size > _MAX_REQUEST_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Payload too large")
