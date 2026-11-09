"""Pydantic schemas for knowledge base chunks and retrieval results."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    """Metadata attached to an indexed document chunk."""

    doc_id: str = Field(description="Starter corpus document ID, e.g. KB-01..KB-09")
    title: str = Field(description="Canonical document title")
    section: str = Field(description="Hierarchical section path, e.g. '1. أدوية الربو > 1. SABA > موانع الاستعمال'")
    chunk_id: str = Field(description="Unique deterministic chunk ID, e.g. 'KB-01-C004'")
    snippet: str = Field(description="Short verbatim excerpt suitable for citations (up to ~280 characters)")
    char_count: int = Field(default=0, description="Character length of chunk text")


class DocumentChunk(BaseModel):
    """A single section-aware text chunk ready for vector embedding and persistence."""

    id: str = Field(description="Unique chunk identifier")
    text: str = Field(description="Full chunk text including breadcrumbs for dense embedding")
    metadata: ChunkMetadata = Field(description="Associated chunk metadata")


class RetrievedChunk(BaseModel):
    """A retrieved chunk returned from vector/hybrid search."""

    doc_id: str
    title: str
    section: str
    chunk_id: str
    snippet: str
    text: str
    score: float = Field(description="Relevance or similarity score (higher is more relevant)")
    rank: int = Field(default=1, description="Rank position (1-based)")
    source: str = Field(default="hybrid", description="Retrieval source: dense, lexical, or hybrid")

    def to_citation_dict(self) -> dict[str, str]:
        """Convert to the exact dictionary format required by the API contract."""
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "section": self.section,
            "snippet": self.snippet,
        }


class IngestionReport(BaseModel):
    """Report produced by the ingestion pipeline."""

    total_documents: int
    total_chunks: int
    chunks_per_document: dict[str, int]
    duration_seconds: float
    manifest_version: str = "1.0.0"
    vector_store_count: int
    storage_path: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
