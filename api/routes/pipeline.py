from __future__ import annotations

from typing import Callable, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from services.orchestrator.pipeline import OrchestratorPipeline


class PipelineRequest(BaseModel):
    path: str
    limit: Optional[int] = 10
    bpm_min: Optional[float] = None
    bpm_max: Optional[float] = None
    mode: Optional[str] = None


def create_pipeline_router(
    pipeline_factory: Callable[[], OrchestratorPipeline] = OrchestratorPipeline,
) -> APIRouter:
    router = APIRouter(tags=["pipeline"])

    @router.post("/pipeline/run")
    def run_pipeline(req: PipelineRequest) -> dict:
        pipeline = pipeline_factory()
        result = pipeline.run(
            path=req.path,
            limit=req.limit or 10,
            bpm_min=req.bpm_min,
            bpm_max=req.bpm_max,
            mode=req.mode,
        )
        return {"status": "ok", "result": result}

    return router


# Backward-compatible export. Application construction uses create_pipeline_router().
router = create_pipeline_router()
