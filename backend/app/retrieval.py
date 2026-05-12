import logging
from typing import Dict, List, Optional, Tuple, TypedDict

import numpy as np

from app.bm25 import BM25Index
from app.ingestion import Chunk
from app.vector_store import store

logger = logging.getLogger(__name__)

RRF_K = 60        # RRF constant — dampens rank differences, standard value
SEMANTIC_TOP_K = 20
BM25_TOP_K = 20
FINAL_TOP_K = 8

# Module-level BM25 index — rebuilt whenever store contents change
_bm25_index: Optional[BM25Index] = None

class RetrievalResult(TypedDict):
    chunks: List[Chunk]
    best_score: float  # highest combined rerank score (0-1), used for threshold check

def build_bm25_index() -> None:
    """Rebuild BM25 index from current store contents. Call after ingestion."""
    global _bm25_index
    chunks = store.get_all_chunks()
    if not chunks:
        logger.warning("build_bm25_index called on empty store — index not built.")
        _bm25_index = None
        return
    _bm25_index = BM25Index.build([c["text"] for c in chunks])
    logger.info("BM25 index rebuilt: %d documents.", len(chunks))


def _cosine_similarity(matrix: np.ndarray, vector: np.ndarray) -> np.ndarray:
    """
    Compute cosine similarity between each row of matrix and vector.
    Both inputs assumed float32. Returns 1-D array of shape (N,).
    """
    norms = np.linalg.norm(matrix, axis=1)
    query_norm = np.linalg.norm(vector)

    # avoid division by zero for zero vectors
    norms = np.where(norms == 0, 1e-10, norms)
    query_norm = query_norm if query_norm != 0 else 1e-10

    return (matrix @ vector) / (norms * query_norm)


def _normalize_scores(scores: List[Tuple[int, float]]) -> List[Tuple[int, float]]:
    """Min-max normalize scores to [0, 1]. Returns original if all scores equal."""
    if not scores:
        return scores
    values = [s for _, s in scores]
    min_v, max_v = min(values), max(values)
    if max_v == min_v:
        return [(idx, 1.0) for idx, _ in scores]
    span = max_v - min_v
    return [(idx, (s - min_v) / span) for idx, s in scores]


def _reciprocal_rank_fusion(
    semantic_results: List[Tuple[int, float]],
    bm25_results: List[Tuple[int, float]],
) -> List[Tuple[int, float]]:
    """
    Merge two ranked lists via RRF: score = Σ 1 / (k + rank).
    Rank is 1-based. k=60 per standard literature.
    """
    rrf_scores: Dict[int, float] = {}

    for rank, (idx, _) in enumerate(semantic_results, start=1):
        rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (RRF_K + rank)

    for rank, (idx, _) in enumerate(bm25_results, start=1):
        rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (RRF_K + rank)

    return sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)


def retrieve(query_embedding: np.ndarray, query_text: str) -> RetrievalResult:
    """
    Hybrid retrieval: semantic + BM25 fused via RRF, re-ranked, top-5 returned.

    Args:
        query_embedding: float32 array of shape (1024,)
        query_text:      raw query string for BM25

    Returns:
        Up to FINAL_TOP_K chunks sorted by combined relevance score.
    """
    chunks = store.get_all_chunks()
    embeddings = store.get_embeddings()

    if not chunks or embeddings is None:
        logger.warning("Retrieval called on empty store — returning no results.")
        return RetrievalResult(chunks=[], best_score=0.0)

    if query_embedding.shape != (embeddings.shape[1],):
        raise ValueError(
            f"Query embedding shape {query_embedding.shape} incompatible "
            f"with store embedding dim {embeddings.shape[1]}"
        )

    # --- Semantic search ---
    similarities = _cosine_similarity(embeddings, query_embedding)
    top_semantic_idx = int(min(SEMANTIC_TOP_K, len(chunks)))
    semantic_ranked = sorted(
        enumerate(similarities.tolist()), key=lambda x: x[1], reverse=True
    )[:top_semantic_idx]

    # --- BM25 keyword search ---
    if _bm25_index is None:
        logger.warning("BM25 index not built — falling back to semantic-only retrieval.")
        bm25_ranked: List[Tuple[int, float]] = []
    else:
        bm25_ranked = _bm25_index.score_query(query_text, top_k=BM25_TOP_K)

    # --- RRF fusion ---
    fused = _reciprocal_rank_fusion(semantic_ranked, bm25_ranked)

    # --- Re-rank: weighted combination of normalized scores ---
    sem_normalized = dict(_normalize_scores(semantic_ranked))
    bm25_normalized = dict(_normalize_scores(bm25_ranked))

    reranked: List[Tuple[int, float]] = []
    for idx, _ in fused[:FINAL_TOP_K * 4]:  # rerank a larger candidate pool
        sem_score = sem_normalized.get(idx, 0.0)
        bm25_score = bm25_normalized.get(idx, 0.0)
        final_score = 0.7 * sem_score + 0.3 * bm25_score
        reranked.append((idx, final_score))

    reranked.sort(key=lambda x: x[1], reverse=True)

    top_chunks = [chunks[idx] for idx, _ in reranked[:FINAL_TOP_K]]
    best_score = reranked[0][1] if reranked else 0.0

    logger.info(
        "Retrieved %d chunks (semantic=%d, bm25=%d, best_score=%.3f) for query: %.60r",
        len(top_chunks), len(semantic_ranked), len(bm25_ranked), best_score, query_text,
    )
    return RetrievalResult(chunks=top_chunks, best_score=best_score)