"""CLI and module runner to parse and ingest knowledge base documents into persistent Chroma.

Usage:
    python -m app.ingestion.run_ingestion [--rebuild] [--doc-id KB-01]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.core.config import get_settings
from app.ingestion.docx_parser import parse_all_manifest_documents, parse_docx_file
from app.retrieval.embedder import get_embedder
from app.retrieval.vector_store import ChromaStore
from app.schemas.chunk import DocumentChunk, IngestionReport

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_ingestion(
    rebuild: bool = True,
    target_doc_id: str | None = None,
    output_report_path: Path | None = None,
) -> IngestionReport:
    """Execute ingestion pipeline for knowledge base documents."""
    settings = get_settings()
    manifest_path = settings.kb_manifest_path
    project_root = settings.project_root

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    vector_store = ChromaStore()

    # Determine which documents to parse
    docs_to_parse = manifest["documents"]
    deleted_manifest = settings.uploads_dir / "deleted_documents.json"
    if deleted_manifest.is_file():
        deleted_ids = set(json.loads(deleted_manifest.read_text(encoding="utf-8")))
        docs_to_parse = [entry for entry in docs_to_parse if entry["doc_id"] not in deleted_ids]
    if target_doc_id:
        docs_to_parse = [d for d in docs_to_parse if d["doc_id"] == target_doc_id]
        if not docs_to_parse:
            raise ValueError(f"Target doc_id '{target_doc_id}' not found in manifest.")
        logger.info(f"Targeted ingestion requested for doc_id='{target_doc_id}'. Live collection preserved until replacement is ready.")
    elif rebuild:
        logger.info("Full rebuild requested. Staging will be populated before live swap.")

    # 1. Parsing (Safe: live store is untouched)
    logger.info(f"Parsing {len(docs_to_parse)} document(s)...")
    start_time = time.perf_counter()
    all_chunks: list[DocumentChunk] = []

    for doc_entry in docs_to_parse:
        # Admin replacements are kept as fixed-ID overrides; full rebuilds must
        # ingest the same source currently represented in the live index.
        override_path = settings.uploads_dir / f"{doc_entry['doc_id']}.docx"
        doc_path = override_path if override_path.is_file() else project_root / doc_entry["relative_path"]
        chunks = parse_docx_file(doc_path, doc_entry["doc_id"], doc_entry["title"])
        all_chunks.extend(chunks)
        logger.info(f"Parsed {doc_entry['doc_id']} ('{doc_entry['title']}'): {len(chunks)} chunks")

    parse_duration = time.perf_counter() - start_time
    logger.info(f"Total chunks parsed: {len(all_chunks)} in {parse_duration:.2f}s")

    # 2. Dense Embedding Generation (Safe: live store is untouched)
    logger.info(f"Generating dense embeddings for {len(all_chunks)} chunks using BAAI/bge-m3...")
    embed_start = time.perf_counter()
    embedder = get_embedder()
    texts = [c.text for c in all_chunks]
    embeddings = embedder.embed_documents(texts, batch_size=32)
    embed_duration = time.perf_counter() - embed_start
    logger.info(f"Generated {len(embeddings)} embeddings in {embed_duration:.2f}s ({len(embeddings)/embed_duration:.1f} chunks/s)")

    # 3. Failure-Safe Persistence into Chroma
    store_start = time.perf_counter()
    if target_doc_id:
        logger.info(f"Committing atomic replacement for '{target_doc_id}'...")
        vector_store.atomic_replace_document(target_doc_id, all_chunks, embeddings)
    elif rebuild:
        logger.info("Committing failure-safe atomic rebuild via staging swap...")
        vector_store.atomic_rebuild(all_chunks, embeddings)
    else:
        logger.info("Upserting chunks into existing collection...")
        vector_store.add_chunks(all_chunks, embeddings)
    store_duration = time.perf_counter() - store_start

    # 4. Collection Statistics & Report Generation
    all_stored = vector_store.get_all_chunks()
    doc_breakdown: dict[str, dict[str, Any]] = {}
    for doc_entry in manifest["documents"]:
        did = doc_entry["doc_id"]
        d_chunks = [c for c in all_stored if c.metadata.doc_id == did]
        avg_chars = sum(c.metadata.char_count for c in d_chunks) / len(d_chunks) if d_chunks else 0.0
        doc_breakdown[did] = {
            "title": doc_entry["title"],
            "chunk_count": len(d_chunks),
            "avg_characters": round(avg_chars, 1),
        }

    total_duration = parse_duration + embed_duration + store_duration
    chunks_per_doc = {did: info["chunk_count"] for did, info in doc_breakdown.items()}

    report = IngestionReport(
        total_documents=len(doc_breakdown),
        total_chunks=len(all_stored),
        chunks_per_document=chunks_per_doc,
        duration_seconds=round(total_duration, 3),
        manifest_version=manifest.get("version", "1.0.0"),
        vector_store_count=vector_store.count(),
        storage_path=str(vector_store.persist_dir),
        details=doc_breakdown,
    )

    # Save report to evaluation results directory
    out_path = output_report_path or (settings.eval_results_dir / "phase2_ingestion_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report_dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_type": f"targeted_{target_doc_id}" if target_doc_id else "full_rebuild",
        "target_doc_id": target_doc_id,
        "total_chunks": report.total_chunks,
        "total_documents": report.total_documents,
        "manifest_version": report.manifest_version,
        "storage_path": report.storage_path,
        "parse_duration_seconds": round(parse_duration, 3),
        "embed_duration_seconds": round(embed_duration, 3),
        "store_duration_seconds": round(store_duration, 3),
        "documents": report.details,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)

    logger.info(f"Ingestion completed successfully. Report written to: {out_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest knowledge base documents into persistent Chroma vector store.")
    parser.add_argument("--rebuild", action="store_true", default=True, help="Rebuild vector collection from scratch.")
    parser.add_argument("--doc-id", type=str, default=None, help="Target specific doc_id to re-index (e.g. KB-01).")
    args = parser.parse_args()

    run_ingestion(rebuild=args.rebuild, target_doc_id=args.doc_id)


if __name__ == "__main__":
    main()
