# SPDX-License-Identifier: MIT
"""CoIR-compatible adapter for grippy's embedder pipeline."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

log = logging.getLogger(__name__)


class GrippyRetriever:
    """Adapts grippy's embedder to CoIR's encode_queries/encode_corpus interface.

    CoIR expects a model object with encode_queries and encode_corpus methods
    that return numpy arrays of embeddings. This adapter wraps any grippy
    Embedder or BatchEmbedder to satisfy that contract.
    """

    def __init__(self, *, embedder: Any, use_batch: bool = False) -> None:
        self._embedder = embedder
        self._use_batch = use_batch and hasattr(embedder, "get_embedding_batch")

    def encode_queries(self, queries: list[str], **kwargs: Any) -> np.ndarray:
        """Encode query strings into embedding vectors."""
        return self._encode_texts(queries)

    def encode_corpus(self, corpus: list[dict[str, str]], **kwargs: Any) -> np.ndarray:
        """Encode corpus documents into embedding vectors.

        CoIR corpus format: list of dicts with 'title' and 'text' keys.
        """
        texts = [f"{doc.get('title', '')} {doc.get('text', '')}".strip() for doc in corpus]
        return self._encode_texts(texts)

    def _encode_texts(self, texts: list[str]) -> np.ndarray:
        """Encode a list of texts into a numpy array of embeddings."""
        if self._use_batch:
            embeddings = self._embedder.get_embedding_batch(texts)
        else:
            embeddings = [self._embedder.get_embedding(t) for t in texts]
        return np.array(embeddings, dtype=np.float32)
