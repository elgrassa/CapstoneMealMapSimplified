"""Adaptive chunking — three strategies, per-collection parameters.

Strategies shipped:
- `recipe_boundary`   — splits on recipe section markers (good for cookbooks)
- `structured_header` — splits on Markdown headers (good for textbooks)
- `sliding_window`    — fallback word-window (generic)

Per-collection size/step defaults live in `COLLECTION_CHUNK_PARAMS`. The demo
values here are neutral starting points that let the capstone reproduce
adaptive behaviour; production at meal-map.app uses tuned values from
internal eval runs.
"""
from __future__ import annotations

import re
from typing import Callable


COLLECTION_CHUNK_PARAMS: dict[str, dict[str, int]] = {
    "recipes": {"size": 120, "step": 60},
    "nutrition_science": {"size": 150, "step": 75},
    "health_food_practical": {"size": 150, "step": 75},
    "medical_dietary_guidelines": {"size": 200, "step": 100},
    "natural_medicine_experimental": {"size": 150, "step": 75},
}

COLLECTION_CHUNK_STRATEGIES: dict[str, str] = {
    "recipes": "recipe_boundary",
    "nutrition_science": "structured_header",
    "health_food_practical": "structured_header",
    "medical_dietary_guidelines": "structured_header",
    "natural_medicine_experimental": "sliding_window",
}


_RECIPE_BOUNDARY_PATTERN = re.compile(
    r"(?im)^\s*(?:recipe|#\s*recipe|##\s*\d+\.|ingredients?\s*[:\-]|servings?\s*[:\-])",
    re.MULTILINE,
)

_HEADER_PATTERN = re.compile(r"(?m)^#{1,3}\s+.+$")


def chunk_sliding_window(text: str, size: int = 100, step: int = 50) -> list[str]:
    """Split `text` into word-windows of `size` words with overlap `size - step`."""
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    for start in range(0, len(words), step):
        window = words[start:start + size]
        if not window:
            break
        chunks.append(" ".join(window))
        if start + size >= len(words):
            break
    return chunks


def chunk_recipe_boundary(text: str, size: int = 120, step: int = 60) -> list[str]:
    """Split on recipe section markers first; fall back to sliding-window inside each section."""
    matches = list(_RECIPE_BOUNDARY_PATTERN.finditer(text))
    if not matches:
        return chunk_sliding_window(text, size, step)

    sections: list[str] = []
    starts = [m.start() for m in matches] + [len(text)]
    for i in range(len(matches)):
        sections.append(text[starts[i]:starts[i + 1]].strip())

    chunks: list[str] = []
    for section in sections:
        if len(section.split()) <= size:
            if section:
                chunks.append(section)
        else:
            chunks.extend(chunk_sliding_window(section, size, step))
    return chunks


def chunk_structured_header(text: str, size: int = 150, step: int = 75) -> list[str]:
    """Split on Markdown headers; fall back to sliding-window inside each section."""
    matches = list(_HEADER_PATTERN.finditer(text))
    if not matches:
        return chunk_sliding_window(text, size, step)

    starts = [m.start() for m in matches] + [len(text)]
    chunks: list[str] = []
    for i in range(len(matches)):
        section = text[starts[i]:starts[i + 1]].strip()
        if not section:
            continue
        if len(section.split()) <= size:
            chunks.append(section)
        else:
            chunks.extend(chunk_sliding_window(section, size, step))
    return chunks


def select_chunker(strategy: str) -> Callable[..., list[str]]:
    if strategy == "recipe_boundary":
        return chunk_recipe_boundary
    if strategy == "structured_header":
        return chunk_structured_header
    return chunk_sliding_window


def build_chunks_adaptive(text: str, collection: str) -> list[str]:
    """Pick the per-collection chunker + size/step and return the chunks."""
    strategy = COLLECTION_CHUNK_STRATEGIES.get(collection, "sliding_window")
    params = COLLECTION_CHUNK_PARAMS.get(collection, {"size": 100, "step": 50})
    chunker = select_chunker(strategy)
    return chunker(text, size=params["size"], step=params["step"])
