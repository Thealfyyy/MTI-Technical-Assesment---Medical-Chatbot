"""Embedding service wrapper for BAAI/bge-m3.

Loads the local cached SentenceTransformer model and provides fast dense vector embeddings.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_EMBEDDER_INSTANCE: Embedder | None = None


class Embedder:
    """Wrapper around SentenceTransformer with caching and device selection."""

    def __init__(self, model_path_or_name: str | Path | None = None, device: str | None = None) -> None:
        settings = get_settings()
        device = device or settings.embedding_device
        self.device = device
        revision = settings.embedding_model_revision or None
        if model_path_or_name is None:
            configured_name = settings.embedding_model_name
            # Check local cache first
            model_cache = settings.sentence_transformers_home / ("models--" + configured_name.replace("/", "--"))
            if model_cache.exists():
                snapshots = model_cache / "snapshots"
                pinned_snapshot = snapshots / revision if snapshots.exists() and revision else None
                if pinned_snapshot is not None and pinned_snapshot.is_dir():
                    model_path = pinned_snapshot
                elif snapshots.exists() and any(snapshots.iterdir()):
                    # Never silently choose a different cached revision.
                    model_path = configured_name
                else:
                    model_path = configured_name
            else:
                model_path = configured_name
        else:
            model_path = Path(model_path_or_name) if isinstance(model_path_or_name, str) and Path(model_path_or_name).exists() else model_path_or_name

        logger.info(f"Loading embedding model from: {model_path} on {device}")
        kwargs = {"device": device}
        if revision and str(model_path) == settings.embedding_model_name:
            kwargs["revision"] = revision
        self.model = SentenceTransformer(str(model_path), **kwargs)
        self.model_name = str(model_path_or_name or settings.embedding_model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Embedding model loaded. Dimension: {self.dimension}")

    def embed_query(self, query: str) -> list[float]:
        """Embed a single search query."""
        vec = self.model.encode(query, normalize_embeddings=True, show_progress_bar=False)
        return vec.tolist() if isinstance(vec, np.ndarray) else list(vec)

    def embed_documents(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Embed a batch of document texts."""
        vecs = self.model.encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
        return vecs.tolist() if isinstance(vecs, np.ndarray) else [list(v) for v in vecs]


def get_embedder(device: str | None = None) -> Embedder:
    """Return the singleton Embedder instance."""
    global _EMBEDDER_INSTANCE
    if _EMBEDDER_INSTANCE is None:
        _EMBEDDER_INSTANCE = Embedder(device=device)
    return _EMBEDDER_INSTANCE
