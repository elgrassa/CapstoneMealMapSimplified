"""RAG router — /query, /query-structured, /agent-query."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from pydantic_agent import run_agent
from agent_config import AgentConfig
from structured_models import CapstoneRAGResponse

router = APIRouter()


class QueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    demo_mode: bool = True


@router.post("/query", response_model=CapstoneRAGResponse)
async def query(req: QueryRequest) -> CapstoneRAGResponse:
    cfg = AgentConfig.from_env()
    if req.top_k is not None:
        cfg.top_k = req.top_k
    cfg.demo_mode = req.demo_mode
    try:
        return run_agent(req.query, cfg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"agent error: {type(e).__name__}: {e}")


@router.post("/agent-query", response_model=CapstoneRAGResponse)
async def agent_query(req: QueryRequest) -> CapstoneRAGResponse:
    """Alias for /query — kept for backward-compatibility with production client."""
    return await query(req)
