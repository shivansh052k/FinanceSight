import json
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from app.ingestion import Chunk

logger = logging.getLogger(__name__)

STORE_PATH = Path(__file__).parent.parent / "data" / "vector_store.json"


class VectorStore:
    """
    Thread-safe in-memory store of chunks + embeddings.
    Persists to and loads from STORE_PATH (JSON with embeddings as float lists).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._chunks: List[Chunk] = []
        self._embeddings: Optional[np.ndarray] = None  # shape (N, 1024)
        self._source_index: Dict[str, List[int]] = {}  # source → chunk indices

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add(self, chunks: List[Chunk], embeddings: np.ndarray) -> None:
        """Append chunks and their embeddings. Thread-safe."""
        if len(chunks) != embeddings.shape[0]:
            raise ValueError(
                f"Chunk count {len(chunks)} != embedding rows {embeddings.shape[0]}"
            )

        with self._lock:
            offset = len(self._chunks)
            self._chunks.extend(chunks)

            if self._embeddings is None:
                self._embeddings = embeddings.astype(np.float32)
            else:
                self._embeddings = np.vstack(
                    [self._embeddings, embeddings.astype(np.float32)]
                )

            for i, chunk in enumerate(chunks):
                self._source_index.setdefault(chunk["source"], []).append(offset + i)
            
            total = len(self._chunks)

        logger.info("Added %d chunks. Store total: %d.", len(chunks), total)

    def clear(self) -> None:
        with self._lock:
            self._chunks = []
            self._embeddings = None
            self._source_index = {}
        logger.info("Vector store cleared.")

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_all_chunks(self) -> List[Chunk]:
        with self._lock:
            return list(self._chunks)

    def get_embeddings(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._embeddings

    def get_sources(self) -> List[str]:
        with self._lock:
            return list(self._source_index.keys())

    def has_source(self, source: str) -> bool:
        with self._lock:
            return source in self._source_index

    def chunk_count(self) -> int:
        with self._lock:
            return len(self._chunks)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persist store to STORE_PATH. Creates parent dirs if needed."""
        with self._lock:
            if not self._chunks:
                logger.warning("Save called on empty store — skipping.")
                return
            chunks_snapshot = list(self._chunks)
            embeddings_snapshot = (
                self._embeddings.tolist() if self._embeddings is not None else []
            )
            source_index_snapshot = {k: list(v) for k, v in self._source_index.items()}

        payload = {
            "chunks": chunks_snapshot,
            "embeddings": embeddings_snapshot,
            "source_index": source_index_snapshot,
        }

        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = STORE_PATH.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            tmp_path.replace(STORE_PATH)  # atomic replace
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        logger.info("Store saved to '%s' (%d chunks).", STORE_PATH, len(chunks_snapshot))

    def load(self) -> None:
        """Load store from STORE_PATH. No-op if file does not exist."""
        if not STORE_PATH.exists():
            logger.info("No persisted store found at '%s' — starting fresh.", STORE_PATH)
            return

        try:
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)

            chunks = payload["chunks"]
            embeddings_list = payload["embeddings"]
            source_index = payload.get("source_index", {})

            if not chunks or not embeddings_list:
                logger.warning("Store file exists but is empty — starting fresh.")
                return

            embeddings = np.array(embeddings_list, dtype=np.float32)

            if embeddings.shape[0] != len(chunks):
                raise ValueError(
                    f"Store corrupt: {len(chunks)} chunks but {embeddings.shape[0]} embeddings"
                )

            with self._lock:
                self._chunks = chunks
                self._embeddings = embeddings
                self._source_index = {
                    k: [int(i) for i in v] for k, v in source_index.items()
                }

            logger.info(
                "Loaded %d chunks from '%s'.", len(self._chunks), STORE_PATH
            )

        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Failed to load vector store: {exc}") from exc


# Module-level singleton — imported by all other modules
store = VectorStore()