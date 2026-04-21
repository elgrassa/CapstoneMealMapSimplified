"""Shared fixtures + path setup for tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "ai" / "week1-rag"))


@pytest.fixture(scope="session", autouse=True)
def _ensure_demo_corpus():
    """Make sure the seed script has been run so tests can retrieve real chunks."""
    demo_root = ROOT / "data" / "rag" / "demo"
    manifest = demo_root / "provenance_manifest.json"
    if not manifest.exists():
        from scripts.seed_demo import main as seed_main  # type: ignore
        seed_main()


@pytest.fixture
def sample_results() -> list[dict]:
    """Minimal retrieved-set fixture for evidence-gate + reranker tests."""
    return [
        {"chunk_id": "a::0001", "score": 0.5, "collection": "nutrition_science", "authority_level": "medium", "source_title": "A"},
        {"chunk_id": "b::0001", "score": 0.2, "collection": "nutrition_science", "authority_level": "high", "source_title": "B"},
        {"chunk_id": "c::0001", "score": 0.05, "collection": "recipes", "authority_level": "medium", "source_title": "C"},
    ]
