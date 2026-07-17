from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter

from core.config.composition_runtime import (
    CompositionRuntimeReadiness,
    evaluate_composition_runtime,
)
from core.config.settings import get_settings


ReadinessProvider = Callable[[], CompositionRuntimeReadiness]


def create_health_router(
    readiness_provider: ReadinessProvider = evaluate_composition_runtime,
) -> APIRouter:
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

    @router.get("/ready")
    def ready() -> dict:
        return readiness_provider().as_dict()

    return router


# Backward-compatible export for external imports. Application construction uses
# create_health_router() to avoid shared mutable router state.
router = create_health_router()
