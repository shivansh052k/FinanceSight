import logging
import re
from typing import List

import numpy as np

from app.embeddings import embed_texts
from app.ingestion import Chunk

logger = logging.getLogger(__name__)

HALLUCINATION_THRESHOLD = 0.40  # sentence similarity below this → removed from answer
MIN_SENTENCE_LEN = 10           # skip fragments, punctuation-only splits

_FILTERED_ANSWER = (
    "The generated answer could not be verified against the source documents. "
    "Please try rephrasing your question."
)


def _split_sentences(text: str) -> List[str]:
    """
    Split text into sentences on .!? boundaries.
    Keeps punctuation attached to the preceding sentence.
    Filters out fragments shorter than MIN_SENTENCE_LEN.
    """
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) >= MIN_SENTENCE_LEN]


def _cosine_similarity_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Compute pairwise cosine similarities between rows of a (M, D) and b (N, D).
    Returns (M, N) matrix. Zero vectors handled via epsilon denominator.
    """
    a_norms = np.linalg.norm(a, axis=1, keepdims=True)
    b_norms = np.linalg.norm(b, axis=1, keepdims=True)

    a_norms = np.where(a_norms == 0, 1e-10, a_norms)
    b_norms = np.where(b_norms == 0, 1e-10, b_norms)

    a_normalized = a / a_norms
    b_normalized = b / b_norms

    return a_normalized @ b_normalized.T  # (M, N)


def filter_hallucinations(answer: str, chunks: List[Chunk]) -> str:
    """
    Remove sentences from answer that cannot be grounded in source chunks.

    Each sentence is embedded and compared against all source chunk embeddings.
    Sentences with max cosine similarity < HALLUCINATION_THRESHOLD are dropped.

    Falls back to original answer on any embedding API failure — infra errors
    should not silently discard content.

    Returns:
        Filtered answer string, or _FILTERED_ANSWER if all sentences are removed.
    """
    if not answer or not answer.strip():
        return answer

    if not chunks:
        logger.warning("Hallucination filter called with no source chunks — returning original.")
        return answer

    sentences = _split_sentences(answer)
    if not sentences:
        logger.warning("No sentences extracted from answer — returning original.")
        return answer

    chunk_texts = [c["text"] for c in chunks]

    try:
        sentence_embeddings = embed_texts(sentences)      # shape (S, 1024)
        chunk_embeddings = embed_texts(chunk_texts)        # shape (C, 1024)
    except Exception as exc:
        logger.error(
            "Hallucination filter: embedding failed (%s) — returning original answer.", exc
        )
        return answer  # fail open — don't silently discard content on infra failure

    # similarity[i, j] = cosine sim between sentence i and chunk j
    similarity = _cosine_similarity_matrix(sentence_embeddings, chunk_embeddings)

    # each sentence passes if its max similarity to any chunk exceeds threshold
    max_similarity_per_sentence = similarity.max(axis=1)  # shape (S,)

    grounded_sentences = [
        sent
        for sent, sim in zip(sentences, max_similarity_per_sentence)
        if sim >= HALLUCINATION_THRESHOLD
    ]

    removed = len(sentences) - len(grounded_sentences)
    if removed > 0:
        logger.info(
            "Hallucination filter removed %d/%d sentence(s) below threshold %.2f.",
            removed, len(sentences), HALLUCINATION_THRESHOLD,
        )

    if not grounded_sentences:
        logger.warning("All sentences failed hallucination check — returning filter message.")
        return _FILTERED_ANSWER

    return " ".join(grounded_sentences)