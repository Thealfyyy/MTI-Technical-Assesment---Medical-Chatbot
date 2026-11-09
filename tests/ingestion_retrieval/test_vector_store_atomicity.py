"""Failure-safety tests for ChromaStore atomic operations.

Covers:
  1. Happy-path full rebuild — staging→live swap produces correct chunk count.
  2. WAL written before first rename — crash simulation between WAL write and
     live→backup rename leaves the WAL file; calling atomic_rebuild again
     recovers correctly via _recover_from_wal().
  3. Crash simulation between live→backup and staging→live renames — WAL is in
     "pre_live_rename" phase; recovery restores live from staging, deletes backup.
  4. Crash simulation after staging→live rename (cleanup phase) — recovery deletes
     stale backup; live collection is intact.
  5. Happy-path document replace — new chunks verified present, obsolete IDs pruned.
  6. Crash simulation: verification failure in atomic_replace_document — obsolete
     chunks survive (no data loss), new chunks present, error is raised.
  7. OOS abstention — retrieve() with min_score threshold returns empty list for
     out-of-scope queries; in-scope queries still return results.

All tests use an isolated temporary Chroma directory (tmp_path) so the live
data/chroma index is never touched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is importable regardless of working directory
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.chunk import ChunkMetadata, DocumentChunk, RetrievedChunk
from app.retrieval.vector_store import COLLECTION_NAME, ChromaStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(doc_id: str, idx: int, text: str = "") -> DocumentChunk:
    """Build a minimal DocumentChunk for testing."""
    chunk_id = f"{doc_id}-chunk-{idx:03d}"
    return DocumentChunk(
        id=chunk_id,
        text=text or f"Test content for {doc_id} chunk {idx}.",
        metadata=ChunkMetadata(
            doc_id=doc_id,
            title=f"Test Doc {doc_id}",
            section=f"Section {idx}",
            chunk_id=chunk_id,
            snippet=f"snippet {idx}",
            char_count=len(text or f"Test content for {doc_id} chunk {idx}."),
        ),
    )


def _make_embeddings(chunks: list[DocumentChunk], dim: int = 8) -> list[list[float]]:
    """Return deterministic fake embeddings (unit vectors) for a chunk list."""
    result = []
    for i, _ in enumerate(chunks):
        vec = [0.0] * dim
        vec[i % dim] = 1.0
        result.append(vec)
    return result


@pytest.fixture()
def store(tmp_path: Path) -> Generator[ChromaStore, None, None]:
    """Isolated ChromaStore backed by a temporary directory."""
    # Patch get_settings so ChromaStore uses tmp_path regardless of .env
    mock_settings = MagicMock()
    mock_settings.chroma_persist_dir = tmp_path / "chroma"
    with patch("app.retrieval.vector_store.get_settings", return_value=mock_settings):
        yield ChromaStore(persist_dir=tmp_path / "chroma")


# ---------------------------------------------------------------------------
# Test 1 — Happy-path full rebuild
# ---------------------------------------------------------------------------

def test_atomic_rebuild_happy_path(store: ChromaStore) -> None:
    """Full rebuild populates the live collection with the correct chunk count."""
    chunks = [_make_chunk("KB-01", i) for i in range(10)]
    embeddings = _make_embeddings(chunks)

    count = store.atomic_rebuild(chunks, embeddings)

    assert count == 10
    assert store.count() == 10
    # WAL must be cleaned up after a successful commit
    assert not store._wal_path.exists(), "WAL file must be deleted after successful rebuild"
    # No leftover staging or backup collections
    collection_names = {c.name for c in store.client.list_collections()}
    assert f"{COLLECTION_NAME}_staging" not in collection_names
    assert f"{COLLECTION_NAME}_backup" not in collection_names


# ---------------------------------------------------------------------------
# Test 2 — WAL recovery from "pre_rename" phase
# (crash happened AFTER WAL written, BEFORE live→backup rename)
# ---------------------------------------------------------------------------

def test_atomic_rebuild_recovery_pre_rename(store: ChromaStore, tmp_path: Path) -> None:
    """WAL phase=pre_rename: live is untouched; staging is complete.

    Simulated by: writing a pre_rename WAL and creating a fully-populated
    staging collection, then constructing a *new* ChromaStore instance that
    triggers _recover_from_wal() on __init__.
    """
    staging_name = f"{COLLECTION_NAME}_staging"
    backup_name = f"{COLLECTION_NAME}_backup"

    # Seed a live collection with OLD data
    old_chunks = [_make_chunk("KB-OLD", i) for i in range(5)]
    old_embeddings = _make_embeddings(old_chunks)
    store.atomic_rebuild(old_chunks, old_embeddings)
    assert store.count() == 5

    # Simulate a NEW rebuild that crashed just after writing the WAL
    new_chunks = [_make_chunk("KB-NEW", i) for i in range(8)]
    new_embeddings = _make_embeddings(new_chunks)

    # Manually populate staging (mimicking what atomic_rebuild did before crash)
    staging_col = store.client.create_collection(
        name=staging_name,
        metadata={"hnsw:space": "cosine"},
    )
    ids = [c.id for c in new_chunks]
    staging_col.upsert(
        ids=ids,
        embeddings=new_embeddings,
        documents=[c.text for c in new_chunks],
        metadatas=[c.metadata.model_dump() for c in new_chunks],
    )

    # Write WAL at pre_rename phase
    store._write_wal("pre_rename", staging_name, backup_name)
    assert store._wal_path.exists()

    # Reconstruct the store (simulates process restart) — recovery runs in __init__
    mock_settings = MagicMock()
    mock_settings.chroma_persist_dir = tmp_path / "chroma"
    with patch("app.retrieval.vector_store.get_settings", return_value=mock_settings):
        recovered = ChromaStore(persist_dir=tmp_path / "chroma")

    assert not recovered._wal_path.exists(), "WAL must be deleted after recovery"
    assert recovered.count() == 8, "Live collection should have new chunks after recovery"
    collection_names = {c.name for c in recovered.client.list_collections()}
    assert staging_name not in collection_names
    assert backup_name not in collection_names


# ---------------------------------------------------------------------------
# Test 3 — WAL recovery from "pre_live_rename" phase
# (crash between live→backup rename and staging→live rename)
# ---------------------------------------------------------------------------

def test_atomic_rebuild_recovery_before_live_rename(store: ChromaStore, tmp_path: Path) -> None:
    """Crash after pre_live_rename WAL write but BEFORE live→backup executes."""
    staging_name = f"{COLLECTION_NAME}_staging"
    backup_name = f"{COLLECTION_NAME}_backup"

    # Seed live
    old_chunks = [_make_chunk("KB-OLD", i) for i in range(4)]
    store.atomic_rebuild(old_chunks, _make_embeddings(old_chunks))

    # Live and staging both still exist: this is the actual pre-operation crash window.
    new_chunks = [_make_chunk("KB-NEW", i) for i in range(6)]
    new_embeddings = _make_embeddings(new_chunks)

    staging_col = store.client.create_collection(name=staging_name, metadata={"hnsw:space": "cosine"})
    staging_col.upsert(
        ids=[c.id for c in new_chunks],
        embeddings=new_embeddings,
        documents=[c.text for c in new_chunks],
        metadatas=[c.metadata.model_dump() for c in new_chunks],
    )
    # Production writes this state before attempting the rename.
    store._write_wal("pre_live_rename", staging_name, backup_name)

    mock_settings = MagicMock()
    mock_settings.chroma_persist_dir = tmp_path / "chroma"
    with patch("app.retrieval.vector_store.get_settings", return_value=mock_settings):
        recovered = ChromaStore(persist_dir=tmp_path / "chroma")

    assert not recovered._wal_path.exists()
    assert recovered.count() == 6
    collection_names = {c.name for c in recovered.client.list_collections()}
    assert staging_name not in collection_names
    assert backup_name not in collection_names


# ---------------------------------------------------------------------------
# Test 4 — WAL recovery from "cleanup" phase
# (crash after staging→live rename, before backup deletion)
# ---------------------------------------------------------------------------

def test_atomic_rebuild_recovery_before_staging_promotion(store: ChromaStore, tmp_path: Path) -> None:
    """Crash after cleanup WAL write but BEFORE staging→live executes."""
    staging_name = f"{COLLECTION_NAME}_staging"
    backup_name = f"{COLLECTION_NAME}_backup"

    # Seed the previous live collection, then simulate the completed live→backup rename.
    old_chunks = [_make_chunk("KB-OLD", i) for i in range(3)]
    store.atomic_rebuild(old_chunks, _make_embeddings(old_chunks))
    store.collection.modify(name=backup_name)

    # Staging contains the complete replacement but has not yet been promoted.
    new_chunks = [_make_chunk("KB-NEW", i) for i in range(7)]
    staging_col = store.client.create_collection(name=staging_name, metadata={"hnsw:space": "cosine"})
    staging_col.upsert(
        ids=[c.id for c in new_chunks],
        embeddings=_make_embeddings(new_chunks),
        documents=[c.text for c in new_chunks],
        metadatas=[c.metadata.model_dump() for c in new_chunks],
    )

    # This WAL write occurs before the production staging→live operation.
    store._write_wal("cleanup", staging_name, backup_name)

    mock_settings = MagicMock()
    mock_settings.chroma_persist_dir = tmp_path / "chroma"
    with patch("app.retrieval.vector_store.get_settings", return_value=mock_settings):
        recovered = ChromaStore(persist_dir=tmp_path / "chroma")

    assert not recovered._wal_path.exists()
    assert recovered.count() == 7, "Complete staging collection must be promoted"
    collection_names = {c.name for c in recovered.client.list_collections()}
    assert staging_name not in collection_names
    assert backup_name not in collection_names


def test_atomic_rebuild_recovery_after_live_rename(store: ChromaStore, tmp_path: Path) -> None:
    """Crash after live→backup completed while WAL still records pre_live_rename."""
    staging_name = f"{COLLECTION_NAME}_staging"
    backup_name = f"{COLLECTION_NAME}_backup"
    old_chunks = [_make_chunk("KB-OLD", i) for i in range(3)]
    store.atomic_rebuild(old_chunks, _make_embeddings(old_chunks))
    new_chunks = [_make_chunk("KB-NEW", i) for i in range(5)]
    staging_col = store.client.create_collection(name=staging_name, metadata={"hnsw:space": "cosine"})
    staging_col.upsert(ids=[c.id for c in new_chunks], embeddings=_make_embeddings(new_chunks),
                       documents=[c.text for c in new_chunks], metadatas=[c.metadata.model_dump() for c in new_chunks])
    store._write_wal("pre_live_rename", staging_name, backup_name)
    store.collection.modify(name=backup_name)

    mock_settings = MagicMock()
    mock_settings.chroma_persist_dir = tmp_path / "chroma"
    with patch("app.retrieval.vector_store.get_settings", return_value=mock_settings):
        recovered = ChromaStore(persist_dir=tmp_path / "chroma")
    assert recovered.count() == 5
    assert not recovered._wal_path.exists()


def test_atomic_rebuild_recovery_after_staging_promotion(store: ChromaStore, tmp_path: Path) -> None:
    """Crash after staging→live completed while WAL still records cleanup."""
    staging_name = f"{COLLECTION_NAME}_staging"
    backup_name = f"{COLLECTION_NAME}_backup"
    # Move the fixture's initially empty live collection aside, then create the
    # prior backup and the already-promoted replacement collection.
    store.collection.modify(name=f"{COLLECTION_NAME}_initial")
    old_chunks = [_make_chunk("KB-OLD", i) for i in range(3)]
    backup_col = store.client.create_collection(name=backup_name, metadata={"hnsw:space": "cosine"})
    backup_col.upsert(
        ids=[c.id for c in old_chunks],
        embeddings=_make_embeddings(old_chunks),
        documents=[c.text for c in old_chunks],
        metadatas=[c.metadata.model_dump() for c in old_chunks],
    )

    new_chunks = [_make_chunk("KB-NEW", i) for i in range(7)]
    new_col = store.client.create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    new_col.upsert(ids=[c.id for c in new_chunks], embeddings=_make_embeddings(new_chunks),
                   documents=[c.text for c in new_chunks], metadatas=[c.metadata.model_dump() for c in new_chunks])
    store.client.delete_collection(f"{COLLECTION_NAME}_initial")
    store._write_wal("cleanup", staging_name, backup_name)

    mock_settings = MagicMock()
    mock_settings.chroma_persist_dir = tmp_path / "chroma"
    with patch("app.retrieval.vector_store.get_settings", return_value=mock_settings):
        recovered = ChromaStore(persist_dir=tmp_path / "chroma")

    assert not recovered._wal_path.exists()
    assert recovered.count() == 7, "Live (new data) must be intact"
    collection_names = {c.name for c in recovered.client.list_collections()}
    assert backup_name not in collection_names


# ---------------------------------------------------------------------------
# Test 5 — Happy-path document replace
# ---------------------------------------------------------------------------

def test_atomic_replace_document_happy_path(store: ChromaStore) -> None:
    """New chunks upserted, verified present, and obsolete chunks pruned."""
    # Seed the collection with KB-01 (3 chunks) and KB-02 (2 chunks)
    kb01_v1 = [_make_chunk("KB-01", i) for i in range(3)]
    kb02 = [_make_chunk("KB-02", i) for i in range(2)]
    all_chunks = kb01_v1 + kb02
    store.atomic_rebuild(all_chunks, _make_embeddings(all_chunks))
    assert store.count() == 5

    # Replace KB-01 with 4 new chunks (different IDs to force prune of old ones)
    kb01_v2 = [_make_chunk("KB-01", i + 100) for i in range(4)]
    count = store.atomic_replace_document("KB-01", kb01_v2, _make_embeddings(kb01_v2))

    assert count == 4
    assert store.count() == 6  # 4 new KB-01 + 2 KB-02

    # Verify old KB-01 chunk IDs are gone
    old_ids = [c.id for c in kb01_v1]
    result = store.collection.get(ids=old_ids, include=[])
    assert result["ids"] == [], "Old KB-01 chunk IDs must be pruned"

    # Verify new KB-01 chunk IDs are present
    new_ids = [c.id for c in kb01_v2]
    result = store.collection.get(ids=new_ids, include=[])
    assert set(result["ids"]) == set(new_ids)


# ---------------------------------------------------------------------------
# Test 6 — atomic_replace_document: verification failure does NOT delete old data
# ---------------------------------------------------------------------------

def test_atomic_replace_document_verification_failure_preserves_data(store: ChromaStore) -> None:
    """If post-upsert verification returns unexpected IDs, old chunks survive."""
    kb01_v1 = [_make_chunk("KB-01", i) for i in range(3)]
    store.atomic_rebuild(kb01_v1, _make_embeddings(kb01_v1))

    kb01_v2 = [_make_chunk("KB-01", i + 50) for i in range(2)]

    # Patch collection.get to simulate verification returning empty ids
    real_get = store.collection.get

    call_count = {"n": 0}

    def patched_get(ids=None, **kwargs):
        call_count["n"] += 1
        if ids is not None and call_count["n"] == 2:
            # Second call is the verification call; return empty to simulate failure
            return {"ids": [], "documents": [], "metadatas": []}
        return real_get(ids=ids, **kwargs)

    store.collection.get = patched_get  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="Post-upsert verification failed"):
        store.atomic_replace_document("KB-01", kb01_v2, _make_embeddings(kb01_v2))

    # Old KB-01 chunks must still exist (no data lost)
    store.collection.get = real_get  # restore
    old_ids = [c.id for c in kb01_v1]
    result = store.collection.get(ids=old_ids, include=[])
    assert len(result["ids"]) == len(old_ids), (
        "Old chunks must survive a failed replacement (no data loss)"
    )


# ---------------------------------------------------------------------------
# Test 7 — OOS abstention via min_score threshold
# ---------------------------------------------------------------------------

def test_retrieve_min_score_abstention() -> None:
    """retrieve(min_score=X) returns empty list when top scores are below threshold.

    Uses a fully-mocked RetrievalService so the test does not load BGE-M3 or Chroma.
    """
    from app.retrieval.service import RetrievalService

    mock_store = MagicMock()
    mock_embedder = MagicMock()
    mock_embedder.embed_query.return_value = [0.0] * 8

    # Simulate low-relevance results (OOS query — all below threshold)
    low_score_chunks = [
        RetrievedChunk(
            doc_id="KB-01", title="T", section="S", chunk_id=f"c-{i}",
            snippet="", text="Unrelated content", score=0.15, rank=i + 1, source="dense",
        )
        for i in range(3)
    ]
    mock_store.query_dense.return_value = low_score_chunks
    mock_store.count.return_value = 10

    mock_bm25 = MagicMock()
    mock_bm25.search.return_value = low_score_chunks

    mock_settings = MagicMock()

    with patch("app.retrieval.service.get_settings", return_value=mock_settings):
        service = RetrievalService(
            embedder=mock_embedder,
            vector_store=mock_store,
            bm25_index=mock_bm25,
        )

    # With threshold 0.35 all low-score chunks are filtered out → empty list
    result_with_threshold = service.retrieve(
        "What is the dosage of Artemether for Malaria?", min_score=0.35, hybrid=True
    )
    assert result_with_threshold == [], (
        "retrieve(min_score=0.35) must return [] when all chunk scores are below threshold"
    )

    # Without threshold the same chunks are returned (backward-compatible default)
    result_no_threshold = service.retrieve(
        "What is the dosage of Artemether for Malaria?", min_score=0.0, hybrid=True
    )
    assert len(result_no_threshold) > 0, (
        "retrieve(min_score=0.0) must return chunks (default behavior preserved)"
    )


# ---------------------------------------------------------------------------
# Test 8 — in-scope queries pass through min_score=0.35 unfiltered
# ---------------------------------------------------------------------------

def test_retrieve_in_scope_above_threshold() -> None:
    """In-scope high-similarity results are NOT filtered by the abstention threshold."""
    from app.retrieval.service import RetrievalService

    mock_store = MagicMock()
    mock_embedder = MagicMock()
    mock_embedder.embed_query.return_value = [0.0] * 8

    high_score_chunks = [
        RetrievedChunk(
            doc_id="KB-07", title="T", section="S", chunk_id=f"c-{i}",
            snippet="", text="Metformin contraindicated in renal impairment eGFR < 30",
            score=0.72, rank=i + 1, source="dense",
        )
        for i in range(3)
    ]
    mock_store.query_dense.return_value = high_score_chunks
    mock_store.count.return_value = 10

    mock_bm25 = MagicMock()
    mock_bm25.search.return_value = high_score_chunks

    mock_settings = MagicMock()

    with patch("app.retrieval.service.get_settings", return_value=mock_settings):
        service = RetrievalService(
            embedder=mock_embedder,
            vector_store=mock_store,
            bm25_index=mock_bm25,
        )

    result = service.retrieve(
        "دوا السكر ميتفورمين ممنوع امتى؟", min_score=0.35, hybrid=True
    )
    assert len(result) > 0, "High-score in-scope chunks must pass the abstention threshold"
