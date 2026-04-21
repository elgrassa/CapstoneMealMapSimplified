"""Pydantic models for chunk + retrieval shapes — demo-minimal."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvidenceTier(str, Enum):
    SUPPORTED = "supported"
    FALLBACK = "fallback"
    REFUSED = "refused"


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    collection: str
    text: str
    source_title: str | None = None
    source_url: str | None = None
    authority_level: Literal["high", "medium", "low"] = "medium"
    safety_sensitive: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    chunk_id: str
    doc_id: str
    collection: str
    text: str
    score: float
    source_title: str | None = None
    source_url: str | None = None
    authority_level: Literal["high", "medium", "low"] = "medium"
    safety_sensitive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
