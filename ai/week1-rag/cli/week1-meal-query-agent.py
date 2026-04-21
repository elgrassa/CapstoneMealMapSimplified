#!/usr/bin/env python3
"""Terminal CLI for the capstone agent — earns the "UI: terminal" rubric bonus (1 pt).

Usage:
    python3 ai/week1-rag/cli/week1-meal-query-agent.py "What is the RDA for vitamin D?"
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make sibling modules importable when run directly
THIS_DIR = Path(__file__).resolve().parent  # ai/week1-rag/cli
AI_DIR = THIS_DIR.parent                    # ai/week1-rag
CAPSTONE_ROOT = AI_DIR.parent.parent         # SimplifiedMealMasterCapstone
sys.path.insert(0, str(AI_DIR))
sys.path.insert(0, str(CAPSTONE_ROOT / "src"))
sys.path.insert(0, str(CAPSTONE_ROOT))

from pydantic_agent import run_agent  # noqa: E402
from agent_config import AgentConfig  # noqa: E402
from backend.services.corpus_manager import load_all_demo_indexes  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: week1-meal-query-agent.py '<your nutrition or recipe question>'")
        return 1
    load_all_demo_indexes()

    query = " ".join(sys.argv[1:])
    cfg = AgentConfig.from_env()
    response = run_agent(query, cfg)

    print(f"\n── Evidence tier: {response.evidence_tier}  (confidence: {response.confidence:.3f}) ──")
    print(f"\n{response.answer}\n")
    if response.citations:
        print("Citations:")
        for c in response.citations:
            print(f"  • {c.source_title} [{c.collection}, score={c.score:.3f}] — chunk={c.chunk_id}")
    if response.requires_disclaimer and response.disclaimer_text:
        print(f"\n[disclaimer] {response.disclaimer_text}")
    if response.demo_blocked_collections:
        print(f"\n[demo mode] These collections are production-only: {response.demo_blocked_collections}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
