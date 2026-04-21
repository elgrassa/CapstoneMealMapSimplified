"""Pydantic response schemas for the agent's structured output.

The agent always returns a `CapstoneRAGResponse` — never free text. This lets
the Streamlit demo render a consistent shape and the eval harness score on
predictable fields.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    chunk_id: str
    source_title: str
    source_url: str | None = None
    collection: str
    authority_level: Literal["high", "medium", "low"] = "medium"
    score: float = Field(ge=0.0)


class ToolCall(BaseModel):
    name: str
    arguments: dict = Field(default_factory=dict)
    result_preview: str | None = None
    duration_ms: int | None = None


class CapstoneRAGResponse(BaseModel):
    """Structured agent output — every field is scorable by the LLM-as-Judge."""

    answer: str = Field(description="The user-facing response text.")
    evidence_tier: Literal["supported", "fallback", "refused"]
    confidence: float = Field(ge=0.0, description="Adjusted top score from the evidence gate (BM25 scores have no natural upper bound).")
    citations: list[Citation] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    requires_disclaimer: bool = False
    disclaimer_text: str | None = None
    demo_blocked_collections: list[str] = Field(default_factory=list)
    reasoning_notes: str | None = Field(
        default=None,
        description="Optional short trace of why the agent picked this evidence tier.",
    )


class AgentQueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    demo_mode: bool = True
    use_preprocessed_corpus: bool = True
    uploaded_text: str | None = None
    uploaded_filename: str | None = None


class JudgeScore(BaseModel):
    criterion: str
    score: int = Field(ge=0, le=1)
    rationale: str


class JudgeResult(BaseModel):
    query: str
    response: str
    scores: list[JudgeScore]
    total: int
    max: int
    pass_threshold: int = Field(default=4, description="Passing score out of 6.")

    @property
    def passed(self) -> bool:
        return self.total >= self.pass_threshold
