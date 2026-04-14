from fastapi import FastAPI

from api.middleware.auth import AuthContextMiddleware
from api.middleware.cors import install_cors
from api.routes.health import router as health_router
from api.routes.jobs import router as jobs_router
from core.config.settings import get_settings
from core.logging.logger import configure_logging, get_logger


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    logger = get_logger(__name__)

    app = FastAPI(
        title=settings.app_name,
        version=settings.api_version,
        debug=settings.app_debug,
    )

    install_cors(app)
    app.add_middleware(AuthContextMiddleware)

    app.include_router(health_router)
    app.include_router(jobs_router)

    logger.info(
        "app_initialized",
        extra={
            "app_name": settings.app_name,
            "env": settings.app_env,
            "security_mode": settings.security_mode,
        },
    )
    return app


app = create_app()
