from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.middleware.request_context import ensure_request_id

logger = logging.getLogger("applaylist.api")


def configure_observability() -> None:
    if logger.handlers:
        return

    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False


def _log(event: str, **payload: Any) -> None:
    body = {"event": event, **payload}
    logger.info(json.dumps(body, ensure_ascii=False, default=str))


async def log_request_response(request: Request, call_next):
    started = time.time()
    request_id = ensure_request_id(request)

    try:
        response = await call_next(request)
        duration_ms = round((time.time() - started) * 1000, 2)

        if not response.headers.get("X-Request-ID"):
            response.headers["X-Request-ID"] = request_id

        _log(
            "request_complete",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
    except Exception as exc:
        duration_ms = round((time.time() - started) * 1000, 2)
        _log(
            "request_exception",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            error=repr(exc),
            duration_ms=duration_ms,
        )
        raise


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = ensure_request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "http_error",
                "message": exc.detail,
                "status_code": exc.status_code,
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = ensure_request_id(request)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "type": "validation_error",
                "message": "Request validation failed",
                "status_code": 422,
                "request_id": request_id,
                "details": exc.errors(),
            }
        },
        headers={"X-Request-ID": request_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = ensure_request_id(request)
    _log(
        "unhandled_exception",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        error=repr(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "type": "internal_error",
                "message": "Internal server error",
                "status_code": 500,
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )
