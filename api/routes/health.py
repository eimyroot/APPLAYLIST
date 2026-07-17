from __future__ import annotations

from fastapi import APIRouter

from core.config.settings import get_settings


def create_health_router() -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    def health() -> dict:
        settings = get_settings()
        return {
            "status": "ok",
            "app": settings.app_name,
            "env": settings.app_env,
            "api_version": settings.api_version,
        }

    return router


# Backward-compatible export for external imports. Application construction uses
# create_health_router() to avoid shared mutable router state.
router = create_health_router()
