"""Agent configuration — shared across pydantic_agent.py and the Streamlit demo."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AgentConfig:
    """Configuration for the capstone PydanticAI agent.

    Attributes:
        model: LLM identifier in PydanticAI format (e.g. ``openai:gpt-4.1-mini``).
        max_iterations: Max tool-calling iterations before forcing a final answer.
        top_k: Default retrieval results to return.
        temperature: LLM sampling temperature.
        request_timeout: Per-request timeout (seconds).
        demo_mode: When True, router allow-lists only `recipes` + `nutrition_science`.
    """

    model: str = "openai:gpt-4.1-mini"
    max_iterations: int = 5
    top_k: int = 6
    temperature: float = 0.1
    request_timeout: int = 30
    demo_mode: bool = True

    @classmethod
    def from_env(cls) -> "AgentConfig":
        return cls(
            model=os.getenv("CAPSTONE_AGENT_MODEL", cls.model),
            max_iterations=int(os.getenv("CAPSTONE_AGENT_MAX_ITERATIONS", str(cls.max_iterations))),
            top_k=int(os.getenv("CAPSTONE_AGENT_TOP_K", str(cls.top_k))),
            temperature=float(os.getenv("CAPSTONE_AGENT_TEMPERATURE", str(cls.temperature))),
            request_timeout=int(os.getenv("CAPSTONE_AGENT_TIMEOUT", str(cls.request_timeout))),
            demo_mode=os.getenv("DEMO_MODE", "true").lower() == "true",
        )
