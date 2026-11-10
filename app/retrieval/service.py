"""Unified Retrieval Service for the MTI Medical Chatbot.

Orchestrates query normalization, dense semantic retrieval (BGE-M3),
lexical keyword matching (BM25), and Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.ingestion.docx_parser import parse_all_manifest_documents
from app.retrieval.embedder import Embedder, get_embedder
from app.retrieval.franco_normalizer import (
    is_likely_franco,
    normalize_franco_to_arabic,
)
from app.retrieval.hybrid_search import (
    SimpleBM25Index,
    expand_corpus_aliases,
    reciprocal_rank_fusion,
)
from app.retrieval.vector_store import ChromaStore
from app.schemas.chunk import DocumentChunk, RetrievedChunk

logger = logging.getLogger(__name__)

_SERVICE_INSTANCE: RetrievalService | None = None

# The corpus is organized under the same section headings for every drug class,
# so an explicit question about one aspect (side effects, contraindications, …)
# can be routed to that section. Without this, a question such as "side effects
# of salbutamol" is answered from whichever section the dense embedding happens
# to score highest, which is often Contraindications.
_SECTION_INTENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"side[\s-]?effects?|adverse|جانبي|الجانبية"), "Side Effects"),
    (re.compile(r"contraindicat|موانع|تحذير|ممنوع|يمنع"), "Contraindications"),
    (re.compile(r"trade[\s-]?names?|brands?|بدائل|الاسم التجاري|أسماء تجارية"), "Trade Names"),
    (re.compile(r"indication|دواعي|الاستخدام"), "Indications"),
    (re.compile(r"interact|تفاعل|تداخل|تعارض|alcohol|كحول"), "Interactions"),
)


def _section_intent(query: str) -> str | None:
    """Return the corpus section heading an explicit aspect question asks about."""
    lowered = query.casefold()
    for pattern, label in _SECTION_INTENTS:
        if pattern.search(lowered):
            return label
    return None


class RetrievalService:
    """End-to-end medical knowledge retrieval service with hybrid search support."""

    def __init__(
        self,
        embedder: Embedder | None = None,
        vector_store: ChromaStore | None = None,
        bm25_index: SimpleBM25Index | None = None,
    ) -> None:
        self.settings = get_settings()
        self.embedder = embedder or get_embedder()
        self.vector_store = vector_store or ChromaStore()
        self._bm25_index = bm25_index
        self._chunks: list[DocumentChunk] = []

    def get_bm25_index(self) -> SimpleBM25Index:
        """Lazily initialize or return the in-memory BM25 index."""
        if self._bm25_index is None:
            if not self._chunks:
                # Fast path: load indexed chunks directly from Chroma
                self._chunks = self.vector_store.get_all_chunks()
                if not self._chunks:
                    # Fallback to parsing if vector store is not yet populated
                    self._chunks = parse_all_manifest_documents(
                        self.settings.kb_manifest_path,
                        self.settings.project_root,
                    )
            self._bm25_index = SimpleBM25Index(self._chunks)
        return self._bm25_index

    def refresh_bm25_index(self) -> None:
        """Reload all chunks directly from Chroma (or manifest fallback) and rebuild BM25 index."""
        self._chunks = self.vector_store.get_all_chunks()
        if not self._chunks:
            self._chunks = parse_all_manifest_documents(
                self.settings.kb_manifest_path,
                self.settings.project_root,
            )
        self._bm25_index = SimpleBM25Index(self._chunks)

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        hybrid: bool = True,
        min_score: float = 0.0,
    ) -> list[RetrievedChunk]:
        """Retrieve the top-k most relevant clinical chunks for a given query.

        Parameters
        ----------
        query:
            The user's raw query string (any supported language/script).
        top_k:
            Maximum number of chunks to return.
        hybrid:
            When True, fuses dense BGE-M3 and BM25 scores via RRF.
            When False, returns dense-only results.
        min_score:
            Minimum dense cosine similarity threshold (0.0–1.0).  Applied to
            the BGE-M3 dense similarity scores BEFORE fusion.  When the best
            dense similarity score is below this threshold, the query has no
            semantically relevant content in the knowledge base; the method
            returns an empty list, which callers should treat as a no-hit /
            abstention signal.  Default 0.0 (no filtering) preserves backward
            compatibility.

            Note: RRF fusion scores are in a different range (~0.01–0.03) and
            are NOT suitable for threshold comparison.  The ``min_score`` filter
            is intentionally applied to the dense scores that reflect true
            semantic similarity.
        """
        if not query or not query.strip():
            return []

        # 1. Query Preprocessing & Franco Normalization
        original_query = query.strip()
        arabic_query = normalize_franco_to_arabic(original_query)
        is_franco = is_likely_franco(original_query)

        # The corpus writes trade names in Latin script. An Arabic transliteration
        # ("بروفين") or a Franco spelling that resolves to one ("brofen") is
        # bridged to the corpus spelling here, because otherwise the query scores
        # just under the abstention threshold and is wrongly reported as
        # out of scope. The user's own wording is kept, not replaced.
        normalized_query = expand_corpus_aliases(
            f"{original_query} {arabic_query}" if is_franco else original_query
        )

        # 2. Dense Vector Retrieval
        query_for_embed = normalized_query
        query_vector = self.embedder.embed_query(query_for_embed)
        dense_results = self.vector_store.query_dense(query_vector, top_k=max(10, top_k * 2))

        # 3. Lexical / BM25 Retrieval
        bm25 = self.get_bm25_index()
        # Combine original tokens (for exact trade names) and Arabic tokens (for symptoms)
        lexical_query = normalized_query
        # A distinctive, capitalized name in the question (a trade name such as
        # "Controloc") is an exact lookup. It is kept separate from fusion
        # because a chunk that appears only in the lexical list always loses to
        # every dense candidate under weighted RRF, and because a Franco-Arabic
        # query can score below the dense threshold even when the name matches.
        exact_matches = (
            bm25.exact_term_matches(lexical_query, top_k=top_k)
            if isinstance(bm25, SimpleBM25Index)
            else []
        )

        # 2a. Early-exit abstention gate based on dense similarity
        # If the best dense score is below the threshold and no exact name match
        # exists, the KB has no relevant content for this query — return empty.
        if min_score > 0.0:
            dense_results = [c for c in dense_results if c.score >= min_score]
            if not dense_results:
                return exact_matches[:top_k]

        if not hybrid:
            return dense_results[:top_k]

        lexical_results = bm25.search(lexical_query, top_k=max(10, top_k * 2))

        # Chunks that lexically match the question *and* sit in the section it
        # asks about take priority over fusion, which prefers dense neighbours.
        intent = _section_intent(normalized_query)
        section_matches = [chunk for chunk in lexical_results if intent in chunk.section] if intent else []
        if intent and exact_matches:
            class_paths = {chunk.section.rsplit(" > ", 1)[0] for chunk in exact_matches}
            same_class = [
                chunk for chunk in section_matches if any(chunk.section.startswith(path) for path in class_paths)
            ]
            section_matches = same_class

        # 4. Reciprocal Rank Fusion (uses filtered dense_results so OOS chunks
        # that slipped through BM25 cannot rescue a query that failed dense gating)
        fused = reciprocal_rank_fusion(
            dense_results=dense_results,
            lexical_results=lexical_results,
            top_k=top_k,
            dense_weight=0.65,
            lexical_weight=0.35,
        )

        # Chunks naming the exact drug/brand are primary, sorted with the matching intent heading first
        candidate_priority = exact_matches + section_matches if exact_matches else section_matches
        if intent and candidate_priority:
            matching_intent = [c for c in candidate_priority if intent in c.section]
            other_priority = [c for c in candidate_priority if intent not in c.section]
            priority = matching_intent + other_priority
        else:
            priority = candidate_priority

        if priority:
            merged: list[RetrievedChunk] = []
            seen: set[str] = set()
            for chunk in priority + fused:
                if chunk.chunk_id not in seen:
                    seen.add(chunk.chunk_id)
                    merged.append(chunk)
            return merged[:top_k]

        return fused


def get_retrieval_service() -> RetrievalService:
    """Return the singleton RetrievalService instance."""
    global _SERVICE_INSTANCE
    if _SERVICE_INSTANCE is None:
        _SERVICE_INSTANCE = RetrievalService()
    return _SERVICE_INSTANCE
