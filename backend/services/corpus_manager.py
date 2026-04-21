"""Load baked demo indexes into the agent tool registry at backend startup."""
from __future__ import annotations

import pickle
from pathlib import Path

from agent_tools_v2 import register_index
from mealmaster_ai.rag.config import DEMO_COLLECTIONS, default_config
from mealmaster_ai.rag.pipeline import build_index, load_chunks_jsonl


def load_all_demo_indexes() -> dict[str, bool]:
    """Find demo chunks + indexes, register each collection's index with the tool layer.

    Returns: {collection: loaded_ok}. Missing indexes are logged but not fatal.
    """
    cfg = default_config()
    loaded: dict[str, bool] = {}
    for collection in DEMO_COLLECTIONS:
        idx_path = cfg.collection_index(collection) / "bm25.pkl"
        chunks_path = cfg.collection_chunks(collection) / "chunks.jsonl"
        index = None
        if idx_path.exists():
            try:
                with open(idx_path, "rb") as f:
                    index = pickle.load(f)
            except Exception:
                index = None
        if index is None and chunks_path.exists():
            docs = load_chunks_jsonl(chunks_path)
            if docs:
                index = build_index(docs)
        if index is not None:
            register_index(collection, index)
            loaded[collection] = True
        else:
            loaded[collection] = False
    return loaded


if __name__ == "__main__":
    result = load_all_demo_indexes()
    print(f"Loaded demo indexes: {result}")
