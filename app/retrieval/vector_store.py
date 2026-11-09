"""Persistent vector store manager using embedded ChromaDB.

Provides document insertion, chunk deletion, re-indexing, and dense vector querying
with metadata preservation (doc_id, title, section, snippet).

Atomicity strategy
------------------
Full rebuilds use a Write-Ahead Log (WAL) file to coordinate the multi-step rename
sequence so that any crash can be diagnosed and recovered on the next startup.

WAL phases are written as intent before each collection operation. Since a crash
can happen either before or after the operation, startup recovery uses the actual
live/staging/backup collection names and can safely repeat the required actions.

Document replacement uses a verify-then-delete pattern: new chunks are upserted and
their presence confirmed via ``collection.get`` before obsolete IDs are deleted.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings
from app.schemas.chunk import ChunkMetadata, DocumentChunk, RetrievedChunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "medical_knowledge_base"

# WAL file is stored alongside the Chroma data directory
_WAL_FILENAME = "atomic_rebuild_wal.json"


class ChromaStore:
    """Manages the persistent ChromaDB collection for medical knowledge base chunks."""

    def __init__(self, persist_dir: Path | None = None) -> None:
        settings = get_settings()
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._wal_path = self.persist_dir / _WAL_FILENAME

        logger.info(f"Initializing ChromaDB client at: {self.persist_dir}")
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False, is_persistent=True),
        )

        # Placeholder — will be set properly after WAL recovery (or fresh init below)
        self.collection: chromadb.Collection = None  # type: ignore[assignment]

        # Run WAL recovery BEFORE get_or_create_collection so that if the live
        # collection was absent (renamed to backup mid-swap), recovery restores it
        # first; otherwise get_or_create would create an empty collection and the
        # subsequent staging→live rename would fail with a uniqueness conflict.
        self._recover_from_wal()

        # If recovery did not set self.collection (no WAL or WAL was a no-op),
        # get or create the live collection normally.
        if self.collection is None:
            self.collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"description": "MTI Medical Chatbot Clinical Knowledge Base", "hnsw:space": "cosine"},
            )

    # ------------------------------------------------------------------
    # WAL helpers
    # ------------------------------------------------------------------

    def _write_wal(self, phase: str, staging: str, backup: str) -> None:
        """Durably replace the WAL before the associated collection operation."""
        temp_path = self._wal_path.with_suffix(self._wal_path.suffix + ".tmp")
        payload = json.dumps({"phase": phase, "staging": staging, "backup": backup})
        with temp_path.open("w", encoding="utf-8", newline="\n") as wal_file:
            wal_file.write(payload)
            wal_file.flush()
            os.fsync(wal_file.fileno())
        os.replace(temp_path, self._wal_path)

    def _delete_wal(self) -> None:
        """Remove WAL file after a clean commit."""
        try:
            self._wal_path.unlink(missing_ok=True)
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Could not delete WAL file: {exc}")

    def _recover_from_wal(self) -> None:
        """Roll forward an interrupted collection swap from observed collection state.

        WAL phases are written before operations, so a phase alone cannot tell
        whether its operation happened before a crash. Recovery therefore uses
        the actual live/staging/backup collection names and is safe to retry.
        """
        if not self._wal_path.exists():
            return

        try:
            wal = json.loads(self._wal_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Rebuild WAL is unreadable at {self._wal_path}; refusing to open the index") from exc

        staging_name = wal.get("staging")
        backup_name = wal.get("backup")
        if staging_name != f"{COLLECTION_NAME}_staging" or backup_name != f"{COLLECTION_NAME}_backup":
            raise RuntimeError(f"Rebuild WAL contains unexpected collection names; refusing recovery: {wal!r}")
        if wal.get("phase") not in {"pre_rename", "pre_live_rename", "cleanup"}:
            raise RuntimeError(f"Rebuild WAL has an unknown phase; refusing recovery: {wal!r}")

        logger.warning(f"WAL detected (phase={wal.get('phase')!r}); recovering from observed collection state")
        existing = {c.name for c in self.client.list_collections()}
        has_live = COLLECTION_NAME in existing
        has_staging = staging_name in existing
        has_backup = backup_name in existing

        # A complete staging collection means the rebuild can be rolled forward.
        # This handles both sides of each WAL-before-operation crash window.
        if has_staging:
            if has_live and not has_backup:
                self._write_wal("pre_live_rename", staging_name, backup_name)
                self.client.get_collection(COLLECTION_NAME).modify(name=backup_name)
                has_live = False
                has_backup = True
            if not has_live:
                self._write_wal("cleanup", staging_name, backup_name)
                self.client.get_collection(staging_name).modify(name=COLLECTION_NAME)
                has_live = True
                has_staging = False

        # If staging is unavailable, preserve/restore the best known complete index.
        if not has_live and has_backup:
            self.client.get_collection(backup_name).modify(name=COLLECTION_NAME)
            has_live = True
            has_backup = False
        if not has_live:
            raise RuntimeError(
                "Cannot recover interrupted index rebuild: no live, complete staging, or backup collection exists. "
                f"WAL retained at {self._wal_path} for manual recovery."
            )

        self.collection = self.client.get_collection(COLLECTION_NAME)
        existing = {c.name for c in self.client.list_collections()}
        if staging_name in existing:
            self.client.delete_collection(staging_name)
        if backup_name in existing:
            self.client.delete_collection(backup_name)
        self._delete_wal()
        logger.info("WAL recovery complete; live collection is available.")

    # ------------------------------------------------------------------
    # Core collection helpers
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return total number of chunks currently indexed in the collection."""
        return self.collection.count()

    def add_chunks(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> int:
        """Add document chunks and their dense embeddings to Chroma."""
        if not chunks:
            return 0

        ids = [c.id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [c.metadata.model_dump() for c in chunks]

        # Chroma upsert allows atomic replacement without duplicate ID collision
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(f"Upserted {len(chunks)} chunks into '{COLLECTION_NAME}' (Total now: {self.count()})")
        return len(chunks)

    def atomic_rebuild(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> int:
        """Atomically rebuild the collection with WAL-coordinated failure-safe swap.

        Strategy
        --------
        1. Remove leftover staging/backup from any prior interrupted run.
        2. Populate staging collection (live is never touched during this phase).
        3. Verify staging count matches expected.
        4. Write WAL phase="pre_rename" (crash here → no data lost; retry on next run).
        5. Rename live → backup  (WAL phase="pre_live_rename").
        6. Rename staging → live (WAL phase="cleanup").
        7. Delete backup.
        8. Delete WAL.

        WAL-based recovery on startup handles crashes at any step.  Live data is
        always either the previous collection (steps 1–4) or the new data (steps 6–8).
        """
        if not chunks or len(chunks) != len(embeddings):
            raise ValueError(f"Chunk count ({len(chunks)}) must match embedding count ({len(embeddings)}) and be > 0.")

        staging_name = f"{COLLECTION_NAME}_staging"
        backup_name = f"{COLLECTION_NAME}_backup"

        # Step 1: Remove any stale staging/backup that could confuse WAL recovery.
        # Only safe to do when no WAL file exists (i.e., no interrupted run).
        if not self._wal_path.exists():
            existing_names = {c.name for c in self.client.list_collections()}
            if staging_name in existing_names:
                self.client.delete_collection(staging_name)
            if backup_name in existing_names:
                self.client.delete_collection(backup_name)

        # Step 2: Populate staging (live is untouched — crash here is fully safe)
        logger.info(f"Populating staging collection '{staging_name}' with {len(chunks)} chunks...")
        staging_col = self.client.create_collection(
            name=staging_name,
            metadata={"description": "MTI Medical Chatbot Staging Collection", "hnsw:space": "cosine"},
        )

        ids = [c.id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [c.metadata.model_dump() for c in chunks]

        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            staging_col.upsert(
                ids=ids[i : i + batch_size],
                embeddings=embeddings[i : i + batch_size],
                documents=documents[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
            )

        # Step 3: Verify staging before touching the live collection
        staged_count = staging_col.count()
        if staged_count != len(chunks):
            self.client.delete_collection(staging_name)
            raise RuntimeError(
                f"Staging count mismatch: expected {len(chunks)}, got {staged_count}. "
                "Rebuild aborted; live collection preserved."
            )

        # Step 4: Write WAL — from this point crashes are recoverable
        self._write_wal("pre_rename", staging_name, backup_name)

        # Step 5: Rename live → backup
        existing_names = {c.name for c in self.client.list_collections()}
        if COLLECTION_NAME in existing_names:
            live_col = self.client.get_collection(COLLECTION_NAME)
            self._write_wal("pre_live_rename", staging_name, backup_name)
            live_col.modify(name=backup_name)

        # Step 6: Rename staging → live
        self._write_wal("cleanup", staging_name, backup_name)
        staging_col.modify(name=COLLECTION_NAME)
        self.collection = self.client.get_collection(COLLECTION_NAME)

        # Step 7: Delete backup (safe; live is already the new data)
        existing_names = {c.name for c in self.client.list_collections()}
        if backup_name in existing_names:
            self.client.delete_collection(backup_name)

        # Step 8: Remove WAL — operation is fully committed
        self._delete_wal()

        logger.info(f"Atomic rebuild complete: {staged_count} chunks committed to '{COLLECTION_NAME}'")
        return staged_count

    def atomic_replace_document(
        self,
        doc_id: str,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> int:
        """Replace chunks for a single document using verify-then-delete semantics.

        Failure-safety strategy
        -----------------------
        The caller must embed all chunks BEFORE calling this method.  If embedding
        fails, the live collection is never touched.

        Once inside this method:
        1. Record existing chunk IDs for the doc so we know what to prune later.
        2. Upsert all new chunks into the live collection (idempotent — safe to retry).
        3. Verify every new chunk ID is present via ``collection.get`` before touching
           old data.  If verification fails, raise and leave the collection in a
           consistent state (new chunks upserted but nothing deleted — recoverable on
           retry since upsert is idempotent).
        4. Only after successful verification delete the obsolete IDs.

        A crash between steps 2 and 4 leaves new AND old chunk IDs for the same
        doc_id in the collection.  On retry, step 2 is idempotent; step 3 succeeds;
        step 4 cleans up the same stale IDs.  No data is permanently lost.
        """
        if not chunks or len(chunks) != len(embeddings):
            raise ValueError(f"Chunk count ({len(chunks)}) must match embedding count ({len(embeddings)}) and be > 0.")
        for c in chunks:
            if c.metadata.doc_id != doc_id:
                raise ValueError(f"Chunk doc_id '{c.metadata.doc_id}' does not match target doc_id '{doc_id}'.")

        # Step 1: Record existing chunk IDs (determines what to prune later)
        existing_data = self.collection.get(where={"doc_id": doc_id})
        existing_ids = set(existing_data["ids"]) if existing_data and "ids" in existing_data else set()

        # Step 2: Upsert new chunks (live collection untouched prior to this point
        # if any embedding/prep step in the caller raised an exception)
        ids = [c.id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [c.metadata.model_dump() for c in chunks]

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        # Step 3: Verify new chunks are durably present before deleting anything
        verification = self.collection.get(ids=ids, include=[])
        verified_ids = set(verification["ids"]) if verification and "ids" in verification else set()
        missing = set(ids) - verified_ids
        if missing:
            raise RuntimeError(
                f"Post-upsert verification failed for doc_id='{doc_id}': "
                f"{len(missing)} chunk(s) not found after upsert ({sorted(missing)[:3]}…). "
                "Obsolete chunks were NOT deleted; retry is safe."
            )

        # Step 4: Prune obsolete chunks only after successful verification
        new_ids = set(ids)
        obsolete_ids = list(existing_ids - new_ids)
        if obsolete_ids:
            self.collection.delete(ids=obsolete_ids)
            logger.info(f"Pruned {len(obsolete_ids)} obsolete chunk(s) for doc_id='{doc_id}'")

        logger.info(f"Atomic replacement complete: doc_id='{doc_id}' now has {len(chunks)} chunks active.")
        return len(chunks)

    def get_all_chunks(self) -> list[DocumentChunk]:
        """Fetch all indexed DocumentChunks with full text and metadata directly from Chroma."""
        if self.count() == 0:
            return []
        data = self.collection.get(include=["documents", "metadatas"])
        chunks: list[DocumentChunk] = []
        for chunk_id, doc_text, meta in zip(data["ids"], data["documents"], data["metadatas"]):
            chunks.append(
                DocumentChunk(
                    id=chunk_id,
                    text=doc_text,
                    metadata=ChunkMetadata(
                        doc_id=str(meta.get("doc_id", "")),
                        title=str(meta.get("title", "")),
                        section=str(meta.get("section", "")),
                        chunk_id=str(meta.get("chunk_id", chunk_id)),
                        snippet=str(meta.get("snippet", doc_text[:120])),
                        char_count=int(meta.get("char_count", len(doc_text))),
                    ),
                )
            )
        return chunks

    def query_dense(self, query_embedding: list[float], top_k: int = 5) -> list[RetrievedChunk]:
        """Perform dense cosine similarity search."""
        if self.count() == 0:
            return []

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.count()),
            include=["documents", "metadatas", "distances"],
        )

        retrieved: list[RetrievedChunk] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return retrieved

        ids = results["ids"][0]
        docs = results["documents"][0] if results["documents"] else [""] * len(ids)
        metas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)
        distances = results["distances"][0] if results["distances"] else [0.0] * len(ids)

        for rank, (chunk_id, doc_text, meta, dist) in enumerate(zip(ids, docs, metas, distances), start=1):
            # Chroma returns cosine distance in [0, 2]; similarity = 1 - (dist / 2) or 1 - dist
            sim_score = max(0.0, 1.0 - float(dist))
            retrieved.append(
                RetrievedChunk(
                    doc_id=str(meta.get("doc_id", "")),
                    title=str(meta.get("title", "")),
                    section=str(meta.get("section", "")),
                    chunk_id=chunk_id,
                    snippet=str(meta.get("snippet", "")),
                    text=doc_text,
                    score=sim_score,
                    rank=rank,
                    source="dense",
                )
            )

        return retrieved

    def delete_document(self, doc_id: str) -> int:
        """Delete all chunks belonging to a specific document ID (e.g. 'KB-01')."""
        before_count = self.count()
        self.collection.delete(where={"doc_id": doc_id})
        after_count = self.count()
        deleted = before_count - after_count
        logger.info(f"Deleted {deleted} chunks for doc_id='{doc_id}'")
        return deleted

    def clear(self) -> None:
        """Clear all entries in the collection."""
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "MTI Medical Chatbot Clinical Knowledge Base", "hnsw:space": "cosine"},
        )
        logger.info("Cleared all chunks from collection.")

    def get_stats(self) -> dict[str, Any]:
        """Return collection status and breakdown of chunks per doc_id."""
        total = self.count()
        if total == 0:
            return {"total_chunks": 0, "by_doc_id": {}}

        # Fetch all metadatas to compute breakdown
        data = self.collection.get(include=["metadatas"])
        doc_counts: dict[str, int] = {}
        for meta in data["metadatas"]:
            doc_id = meta.get("doc_id", "unknown")
            doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1

        return {
            "total_chunks": total,
            "by_doc_id": dict(sorted(doc_counts.items())),
            "persist_dir": str(self.persist_dir),
        }
