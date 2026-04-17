from __future__ import annotations

from fastapi import FastAPI

from api.routes.health import router as health_router
from api.routes.jobs import router as jobs_router
from api.routes.pipeline import router as pipeline_router
from api.security.bootstrap import apply_security_hardening
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from api.middleware.request_context import RequestContextMiddleware
from api.core.observability import (
    configure_observability,
    http_exception_handler,
    log_request_response,
    unhandled_exception_handler,
    validation_exception_handler,
)

configure_observability()

app = FastAPI(
    title="APPLAYLIST API",
    version="0.11.1",
)

apply_security_hardening(app)

app.add_middleware(RequestContextMiddleware)
app.middleware("http")(log_request_response)

app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(pipeline_router)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
