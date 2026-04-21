"""FastAPI app entry — backend for the capstone demo."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "ai" / "week1-rag"))

from backend.routers import rag, health  # noqa: E402
from backend.services.corpus_manager import load_all_demo_indexes  # noqa: E402


def create_app() -> FastAPI:
    app = FastAPI(
        title="MealMaster Capstone — Simplified API",
        version="0.1.0",
        description="Nutrition & recipe RAG agent — see https://meal-map.app for the production product.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.getenv("CORS_ORIGIN", "http://localhost:8502")],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(rag.router, prefix="/api/v1/rag", tags=["rag"])

    @app.on_event("startup")
    async def _startup() -> None:
        load_all_demo_indexes()

    return app


app = create_app()
