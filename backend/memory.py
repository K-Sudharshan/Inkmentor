import json
import logging
import math
import os
from typing import Any, Callable, Dict, List, Optional, Sequence

from backend.llm import call_embedding
from backend.schemas import RetrievedPageMatch, RetrievePageItem, RetrieveResponse

logger = logging.getLogger("inkmentor.memory")

SEEDS_PATH = os.path.join(os.path.dirname(__file__), "seed_embeddings.json")
_SEEDED_PAGES_CACHE: Optional[List[Dict[str, Any]]] = None


def _find_seeds_path() -> Optional[str]:
    candidate_paths = [
        SEEDS_PATH,
        os.path.join(os.getcwd(), "backend", "seed_embeddings.json"),
        os.path.join(os.getcwd(), "seed_embeddings.json"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "seed_embeddings.json"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "public", "seed_embeddings.json"),
    ]
    for p in candidate_paths:
        if os.path.isfile(p):
            return p
    return None


def get_seed_pages() -> List[Dict[str, Any]]:
    """Loads and caches the 6 precomputed seeded page embeddings."""
    global _SEEDED_PAGES_CACHE
    if _SEEDED_PAGES_CACHE is None:
        target_path = _find_seeds_path()
        if target_path and os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    _SEEDED_PAGES_CACHE = json.load(f)
            except Exception as e:
                logger.error(f"Failed to read seed_embeddings.json: {e}")
                _SEEDED_PAGES_CACHE = []
        else:
            logger.warning(f"seed_embeddings.json not found (searched: {SEEDS_PATH})")
            _SEEDED_PAGES_CACHE = []
    return _SEEDED_PAGES_CACHE



def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
    """Computes cosine similarity between two numerical vectors using standard library math."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(x * y for x, y in zip(v1, v2))
    norm1 = math.sqrt(sum(x * x for x in v1))
    norm2 = math.sqrt(sum(y * y for y in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


def retrieve_context(
    query: str,
    pages: Optional[List[RetrievePageItem]] = None,
    threshold: float = 0.65,
    top_k: int = 3,
    embed_func: Optional[Callable[[str], List[float]]] = None,
) -> RetrieveResponse:
    """Embeds the query and retrieves the top matching notebook pages exceeding the similarity threshold."""
    clean_query = query.strip()
    if not clean_query:
        raise ValueError("Query string cannot be empty")

    embedder = embed_func or call_embedding
    query_vector = embedder(clean_query)

    seed_pages = get_seed_pages()
    candidates: List[Dict[str, Any]] = []

    # If client supplied custom pages, index them
    if pages:
        seed_by_page = {s["page"]: s for s in seed_pages}
        seed_by_title = {s["title"].lower(): s for s in seed_pages}

        for cp in pages:
            # Check if this page matches one of our precomputed seeds
            matched_seed = seed_by_page.get(cp.page) or seed_by_title.get(cp.title.lower())
            if matched_seed and "embedding" in matched_seed:
                vec = matched_seed["embedding"]
            else:
                text_to_embed = f"{cp.title}\n{cp.content}" if cp.content else cp.title
                vec = embedder(text_to_embed)

            candidates.append({
                "page": cp.page,
                "title": cp.title,
                "content": cp.content or cp.title,
                "embedding": vec,
            })
    else:
        # Default to the canonical seeded pages
        candidates = [
            {
                "page": s["page"],
                "title": s["title"],
                "content": s["text"],
                "embedding": s["embedding"],
            }
            for s in seed_pages
        ]

    matches: List[RetrievedPageMatch] = []
    for cand in candidates:
        sim = cosine_similarity(query_vector, cand["embedding"])
        if sim >= threshold:
            # Make a concise snippet: replace newlines with semicolons or take key formula
            lines = [line.strip() for line in cand["content"].splitlines() if line.strip()]
            snippet = "; ".join(lines) if lines else cand["title"]
            matches.append(
                RetrievedPageMatch(
                    page=cand["page"],
                    title=cand["title"],
                    snippet=snippet,
                    similarity=round(sim, 4),
                )
            )

    # Sort descending by similarity
    matches.sort(key=lambda m: m.similarity, reverse=True)
    matches = matches[:top_k]

    top_match = matches[0] if matches else None
    return RetrieveResponse(matches=matches, top_match=top_match)
