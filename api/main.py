from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.core.observability import (
    configure_observability,
    http_exception_handler,
    log_request_response,
    unhandled_exception_handler,
    validation_exception_handler,
)
from api.middleware.request_context import RequestContextMiddleware
from api.routes.health import router as health_router
from api.routes.jobs import router as jobs_router
from api.routes.pipeline import router as pipeline_router
from api.security.auth_gate import ApiKeyAuthMiddleware
from api.security.bootstrap import apply_security_hardening
from api.security.settings import SecuritySettings


def create_app(security_settings: SecuritySettings | None = None) -> FastAPI:
    """Build an isolated APPLAYLIST application instance."""
    config = security_settings or SecuritySettings()
    configure_observability()

    application = FastAPI(
        title="APPLAYLIST API",
        version="0.13.1",
    )

    apply_security_hardening(application, config)
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(ApiKeyAuthMiddleware, security_settings=config)
    application.middleware("http")(log_request_response)

    application.include_router(health_router)
    application.include_router(jobs_router)
    application.include_router(pipeline_router)

    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(Exception, unhandled_exception_handler)
    return application


app = create_app()
