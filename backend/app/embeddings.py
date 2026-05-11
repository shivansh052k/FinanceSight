import logging
import os
import time
from typing import List

import numpy as np
from mistralai import Mistral

logger = logging.getLogger(__name__)

EMBED_MODEL = "mistral-embed"
BATCH_SIZE = 32  # Mistral recommended batch size
EMBED_DIM = 1024  # mistral-embed output dimension
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 2.0  # seconds, doubles each retry
# if we hit Mistral rate limit errors during ingestion of all 10 PDFs, bump RETRY_BACKOFF to 3.0


def _get_client() -> Mistral:
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise EnvironmentError("MISTRAL_API_KEY not set in environment")
    return Mistral(api_key=api_key)


def _embed_batch(client: Mistral, texts: List[str]) -> List[List[float]]:
    """Embed one batch with retry on transient failures."""
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = client.embeddings.create(model=EMBED_MODEL, inputs=texts)
            return [item.embedding for item in response.data]
        except Exception as exc:
            if attempt == RETRY_ATTEMPTS:
                raise RuntimeError(
                    f"Embedding failed after {RETRY_ATTEMPTS} attempts: {exc}"
                ) from exc
            wait = RETRY_BACKOFF * (2 ** (attempt - 1))
            logger.warning("Embed attempt %d failed (%s). Retrying in %.1fs.", attempt, exc, wait)
            time.sleep(wait)
    return []  # unreachable — satisfies type checker


def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Embed a list of texts in batches of BATCH_SIZE.
    Returns float32 NumPy array of shape (len(texts), EMBED_DIM).
    """
    if not texts:
        return np.empty((0, EMBED_DIM), dtype=np.float32)

    client = _get_client()
    all_embeddings: List[List[float]] = []

    for batch_start in range(0, len(texts), BATCH_SIZE):
        batch = texts[batch_start: batch_start + BATCH_SIZE]
        logger.debug(
            "Embedding batch %d/%d (%d texts).",
            batch_start // BATCH_SIZE + 1,
            -(-len(texts) // BATCH_SIZE),  # ceiling division
            len(batch),
        )
        embeddings = _embed_batch(client, batch)

        if len(embeddings) != len(batch):
            raise RuntimeError(
                f"Mistral returned {len(embeddings)} embeddings for batch of {len(batch)}"
            )
        all_embeddings.extend(embeddings)

    matrix = np.array(all_embeddings, dtype=np.float32)

    if matrix.shape != (len(texts), EMBED_DIM):
        raise RuntimeError(
            f"Unexpected embedding shape {matrix.shape}, "
            f"expected ({len(texts)}, {EMBED_DIM})"
        )

    logger.info("Embedded %d texts → shape %s.", len(texts), matrix.shape)
    return matrix


def embed_query(text: str) -> np.ndarray:
    """
    Embed a single query string.
    Returns float32 NumPy array of shape (EMBED_DIM,).
    """
    if not text or not text.strip():
        raise ValueError("Query text must not be empty")
    return embed_texts([text])[0]