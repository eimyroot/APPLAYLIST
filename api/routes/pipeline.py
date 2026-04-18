from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from services.orchestrator.pipeline import OrchestratorPipeline

router = APIRouter(tags=["pipeline"])


class PipelineRequest(BaseModel):
    path: str
    limit: Optional[int] = 10
    bpm_min: Optional[float] = None
    bpm_max: Optional[float] = None
    mode: Optional[str] = None


@router.post("/pipeline/run")
def run_pipeline(req: PipelineRequest) -> dict:
    pipeline = OrchestratorPipeline()
    result = pipeline.run(
        path=req.path,
        limit=req.limit or 10,
        bpm_min=req.bpm_min,
        bpm_max=req.bpm_max,
        mode=req.mode,
    )
    return {"status": "ok", "result": result}
