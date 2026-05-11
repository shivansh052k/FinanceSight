import logging
import math
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Okapi BM25 tuning parameters (Robertson et al., TREC 1994)
K1 = 1.5   # term frequency saturation — higher = more weight on repeated terms
B  = 0.75  # length normalization — 1.0 = full, 0.0 = none

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "was", "are", "were", "be", "been",
    "has", "have", "had", "that", "this", "it", "its", "as", "not", "no",
})


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if len(t) > 1 and t not in _STOPWORDS]


class BM25Index:
    """
    Okapi BM25 index over a corpus of text chunks.
    Build once with BM25Index.build(), query with score_query().

    Reference: https://en.wikipedia.org/wiki/Okapi_BM25
    """

    def __init__(
        self,
        doc_tokens: List[List[str]],
        tf_maps: List[Dict[str, int]],
        df: Dict[str, int],
        avgdl: float,
        corpus_size: int,
    ) -> None:
        self._doc_tokens = doc_tokens
        self._tf_maps = tf_maps   # precomputed at build — avoids per-query rebuild
        self._df = df
        self._avgdl = avgdl
        self._corpus_size = corpus_size

    @classmethod
    def build(cls, texts: List[str]) -> "BM25Index":
        """Tokenize corpus and precompute tf_maps, document frequencies, avgdl."""
        if not texts:
            raise ValueError("Cannot build BM25 index on empty corpus")

        doc_tokens: List[List[str]] = [_tokenize(t) for t in texts]
        tf_maps: List[Dict[str, int]] = []
        df: Dict[str, int] = {}

        for tokens in doc_tokens:
            tf_map: Dict[str, int] = {}
            for t in tokens:
                tf_map[t] = tf_map.get(t, 0) + 1
            tf_maps.append(tf_map)
            for term in tf_map:  # tf_map keys are already unique
                df[term] = df.get(term, 0) + 1

        total_tokens = sum(len(t) for t in doc_tokens)
        # guard zero: avgdl=1.0 if all docs empty — prevents ZeroDivisionError in scoring
        avgdl = total_tokens / len(doc_tokens) if total_tokens > 0 else 1.0

        logger.info(
            "BM25 index built: %d docs, %d unique terms, avgdl=%.1f.",
            len(texts), len(df), avgdl,
        )
        return cls(doc_tokens, tf_maps, df, avgdl, len(texts))

    def _idf(self, term: str) -> float:
        """
        Smoothed IDF: log((N - df + 0.5) / (df + 0.5) + 1).
        +1 keeps IDF non-negative even for terms in every document.
        """
        df = self._df.get(term, 0)
        return math.log((self._corpus_size - df + 0.5) / (df + 0.5) + 1)

    def score_query(self, query: str, top_k: int = 20) -> List[Tuple[int, float]]:
        """
        Score all documents against query.
        Returns (doc_index, score) pairs sorted descending, capped at top_k.
        Zero-score documents excluded.
        """
        # deduplicate query terms — BM25 spec sums over unique query terms only
        query_terms = list(set(_tokenize(query)))
        if not query_terms:
            return []

        scores: List[float] = []

        for tokens, tf_map in zip(self._doc_tokens, self._tf_maps):
            doc_len = len(tokens)
            if doc_len == 0:
                scores.append(0.0)
                continue

            # compute length normalization factor once per doc, not per term
            norm = 1 - B + B * doc_len / self._avgdl
            score = 0.0

            for term in query_terms:
                tf = tf_map.get(term, 0)
                if tf == 0:
                    continue
                score += self._idf(term) * (tf * (K1 + 1)) / (tf + K1 * norm)

            scores.append(score)

        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(idx, sc) for idx, sc in ranked[:top_k] if sc > 0.0]