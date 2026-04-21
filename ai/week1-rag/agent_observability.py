"""Per-call observability for the agent — writes newline-delimited JSON to `logs/`.

The monitoring dashboard (`monitoring/dashboard.py`) reads these files.
Fire-and-forget: logging failures never block agent generation.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

DEFAULT_LOG_DIR = Path(__file__).resolve().parent / "logs"

# gpt-4.1-mini pricing per 1K tokens (public, see https://openai.com/api/pricing)
INPUT_COST_PER_1K = 0.0003
OUTPUT_COST_PER_1K = 0.0012


class AgentLogger:
    def __init__(self, log_dir: Path | None = None):
        self.log_dir = log_dir or Path(os.getenv("LOGS_DIR", str(DEFAULT_LOG_DIR)))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"agent-{time.strftime('%Y-%m-%d')}.jsonl"

    def log_call(
        self,
        *,
        query: str,
        response_preview: str,
        tool_calls: list[dict[str, Any]] | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        duration_ms: int = 0,
        evidence_tier: str | None = None,
        model: str = "gpt-4.1-mini",
        success: bool = True,
        error: str | None = None,
    ) -> None:
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "model": model,
            "query": query[:500],
            "response_preview": response_preview[:500],
            "tool_calls": tool_calls or [],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(
                (input_tokens / 1000) * INPUT_COST_PER_1K + (output_tokens / 1000) * OUTPUT_COST_PER_1K,
                6,
            ),
            "duration_ms": duration_ms,
            "evidence_tier": evidence_tier,
            "success": success,
            "error": error,
        }
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass


_default_logger: AgentLogger | None = None


def get_logger() -> AgentLogger:
    global _default_logger
    if _default_logger is None:
        _default_logger = AgentLogger()
    return _default_logger
