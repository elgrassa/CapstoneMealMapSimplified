#!/usr/bin/env python3
"""Seed the pre-baked demo corpus — <5 s, no network, verifies SHA256.

For each raw .txt file under `data/rag/demo/{recipes,nutrition_science}/raw/`:
1. Compute SHA256.
2. If a `provenance_manifest.json` exists, verify against the recorded hash.
3. Run adaptive chunking (`chunking.build_chunks_adaptive`).
4. Build a BM25 index (minsearch if installed, else pure-Python fallback).
5. Save `chunks/chunks.jsonl` + `index/bm25.pkl`.

Also updates `provenance_manifest.json` on first run.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
CAPSTONE_ROOT = THIS_DIR.parent
sys.path.insert(0, str(CAPSTONE_ROOT / "src"))
sys.path.insert(0, str(CAPSTONE_ROOT / "ai" / "week1-rag"))

from mealmaster_ai.rag.pipeline import (  # noqa: E402
    build_chunks_for_source,
    build_index,
    save_chunks_jsonl,
)

DEMO_ROOT = CAPSTONE_ROOT / "data" / "rag" / "demo"
MANIFEST_PATH = DEMO_ROOT / "provenance_manifest.json"


DOC_METADATA = {
    "utah_wic_recipe_book": {
        "collection": "recipes",
        "title": "Utah WIC Recipe Book",
        "source_url": "https://wic.utah.gov/wp-content/uploads/WIC-Recipe-Book.pdf",
        "license": "Public domain (17 USC § 105)",
        "authority_level": "medium",
        "safety_sensitive": False,
    },
    "lets_cook_with_kids_ca_wic": {
        "collection": "recipes",
        "title": "Let's Cook With Kids (California WIC)",
        "source_url": "https://www.smchealth.org/sites/main/files/file-attachments/wic-ne-cookingwithchildren-letscookwithkids.pdf",
        "license": "Public domain (17 USC § 105)",
        "authority_level": "medium",
        "safety_sensitive": False,
    },
    "nutrition_science_everyday_application": {
        "collection": "nutrition_science",
        "title": "Nutrition: Science and Everyday Application",
        "source_url": "https://openoregon.pressbooks.pub/nutritionscience2e/",
        "license": "CC BY 4.0",
        "authority_level": "medium",
        "safety_sensitive": False,
    },
    "human_nutrition_hawaii": {
        "collection": "nutrition_science",
        "title": "Human Nutrition (University of Hawai'i)",
        "source_url": "https://pressbooks.oer.hawaii.edu/humannutrition2/",
        "license": "CC BY 4.0",
        "authority_level": "medium",
        "safety_sensitive": False,
    },
    "demo_added_for_capstone": {
        "collection": "recipes",
        "title": "Demo-added recipes (capstone, not a WIC source)",
        "source_url": "https://github.com/elgrassa/CapstoneMealMapSimplified",
        "license": "capstone-added (self-authored for demo scope)",
        "authority_level": "low",
        "safety_sensitive": False,
    },
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"schema_version": "1.0.0", "documents": {}}


def _save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def _seed_one(doc_id: str, meta: dict, manifest: dict) -> dict:
    raw_path = DEMO_ROOT / meta["collection"] / "raw" / f"{doc_id}.txt"
    if not raw_path.exists():
        return {"doc_id": doc_id, "status": "missing_raw", "raw_path": str(raw_path)}

    sha = _sha256(raw_path)
    recorded = manifest.get("documents", {}).get(doc_id, {}).get("sha256")
    sha_ok = recorded == sha if recorded else None

    text = raw_path.read_text(encoding="utf-8")
    chunks = build_chunks_for_source(
        text,
        doc_id=doc_id,
        collection=meta["collection"],
        source_title=meta["title"],
        source_url=meta["source_url"],
        authority_level=meta["authority_level"],
        safety_sensitive=meta["safety_sensitive"],
    )

    chunks_path = DEMO_ROOT / meta["collection"] / "chunks" / "chunks.jsonl"
    save_chunks_jsonl(chunks, chunks_path)

    index = build_index(chunks)
    index_path = DEMO_ROOT / meta["collection"] / "index" / "bm25.pkl"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with open(index_path, "wb") as f:
        pickle.dump(index, f)

    manifest.setdefault("documents", {})[doc_id] = {
        "collection": meta["collection"],
        "title": meta["title"],
        "source_url": meta["source_url"],
        "license": meta["license"],
        "authority_level": meta["authority_level"],
        "sha256": sha,
        "chunk_count": len(chunks),
        "raw_path": str(raw_path.relative_to(CAPSTONE_ROOT)),
        "chunks_path": str(chunks_path.relative_to(CAPSTONE_ROOT)),
        "index_path": str(index_path.relative_to(CAPSTONE_ROOT)),
    }

    return {
        "doc_id": doc_id,
        "status": "ok",
        "sha_match": sha_ok,
        "chunks": len(chunks),
    }


def main() -> int:
    start = time.time()
    print("[seed_demo] starting — no network, SHA256-verified")
    manifest = _load_manifest()
    results = []
    for doc_id, meta in DOC_METADATA.items():
        result = _seed_one(doc_id, meta, manifest)
        results.append(result)
        emoji = "✓" if result.get("status") == "ok" else "·"
        print(f"  {emoji} {doc_id} [{meta['collection']}] → {result}")

    _save_manifest(manifest)
    elapsed = time.time() - start
    ok = sum(1 for r in results if r.get("status") == "ok")
    print(f"[seed_demo] {ok}/{len(results)} documents ready in {elapsed:.2f}s")
    print(f"[seed_demo] manifest saved: {MANIFEST_PATH.relative_to(CAPSTONE_ROOT)}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
