from fastapi import FastAPI

from api.routes.health import router as health_router
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

    app.include_router(health_router)
    logger.info("app_initialized", extra={"app_name": settings.app_name, "env": settings.app_env})
    return app


app = create_app()
