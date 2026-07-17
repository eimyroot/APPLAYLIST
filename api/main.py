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
from api.routes.health import create_health_router
from api.routes.jobs import create_jobs_router
from api.routes.pipeline import create_pipeline_router
from api.security.auth_gate import ApiKeyAuthMiddleware
from api.security.bootstrap import apply_security_hardening
from api.security.settings import SecuritySettings
from core.config.composition_runtime import (
    CompositionRuntimeReadiness,
    evaluate_composition_runtime,
)


def create_app(
    security_settings: SecuritySettings | None = None,
    composition_readiness: CompositionRuntimeReadiness | None = None,
) -> FastAPI:
    """Build an isolated APPLAYLIST application instance."""
    config = security_settings or SecuritySettings()
    readiness = (
        composition_readiness
        if composition_readiness is not None
        else evaluate_composition_runtime()
    )
    configure_observability()

    application = FastAPI(
        title="APPLAYLIST API",
        version="0.13.1",
    )
    application.state.composition_runtime_readiness = readiness

    apply_security_hardening(application, config)
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(ApiKeyAuthMiddleware, security_settings=config)
    application.middleware("http")(log_request_response)

    application.include_router(
        create_health_router(readiness_provider=lambda: readiness)
    )
    application.include_router(create_jobs_router())
    application.include_router(create_pipeline_router())

    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(Exception, unhandled_exception_handler)
    return application


app = create_app()
