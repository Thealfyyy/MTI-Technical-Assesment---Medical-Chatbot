"""Local-demo document replacement and removal for the fixed starter corpus."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.auth import require_admin
from app.core.config import get_settings
from app.ingestion.docx_parser import parse_docx_file
from app.retrieval.embedder import get_embedder
from app.retrieval.service import get_retrieval_service
from app.retrieval.vector_store import ChromaStore

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_admin)])
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


def _manifest_document(doc_id: str) -> dict:
    settings = get_settings()
    manifest = yaml.safe_load(settings.kb_manifest_path.read_text(encoding="utf-8"))
    for item in manifest.get("documents", []):
        if item.get("doc_id") == doc_id:
            return item
    raise HTTPException(status_code=404, detail="Unknown starter corpus document ID")


def _deleted_ids_path() -> Path:
    return get_settings().uploads_dir / "deleted_documents.json"


def _read_deleted_ids() -> set[str]:
    path = _deleted_ids_path()
    return set(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else set()


def _write_deleted_ids(ids: set[str]) -> None:
    path = _deleted_ids_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(sorted(ids), stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _index_docx(source: Path, doc_id: str, title: str) -> int:
    chunks = parse_docx_file(source, doc_id, title)
    if not chunks:
        raise ValueError("The uploaded document produced no searchable content")
    embeddings = get_embedder().embed_documents([chunk.text for chunk in chunks], batch_size=32)
    if len(embeddings) != len(chunks):
        raise RuntimeError("Embedding count does not match parsed chunk count")
    count = ChromaStore().atomic_replace_document(doc_id, chunks, embeddings)
    return count


@router.get("/admin/documents")
def list_documents() -> list[dict[str, object]]:
    """List all corpus documents, including their active chunk count and operational status."""
    from collections import Counter
    settings = get_settings()
    manifest = yaml.safe_load(settings.kb_manifest_path.read_text(encoding="utf-8"))
    deleted_ids = _read_deleted_ids()
    store = ChromaStore()
    all_chunks = store.get_all_chunks()
    chunk_counts = Counter(c.metadata.doc_id for c in all_chunks)

    docs: list[dict[str, object]] = []
    for item in manifest.get("documents", []):
        doc_id = item["doc_id"]
        is_deleted = doc_id in deleted_ids
        override_file = settings.uploads_dir / f"{doc_id}.docx"
        is_replaced = override_file.is_file() and not is_deleted

        status = "deleted" if is_deleted else ("replaced" if is_replaced else "active")
        docs.append({
            "doc_id": doc_id,
            "title": item.get("title", doc_id),
            "category": item.get("category", "General"),
            "source_file": item.get("source_file", ""),
            "chunks_count": chunk_counts.get(doc_id, 0),
            "status": status,
        })
    return docs


@router.post("/admin/documents")
async def replace_document(doc_id: str = Form(...), file: UploadFile = File(...)) -> dict[str, object]:
    """Replace one starter KB document and re-index it before committing the upload."""
    entry = _manifest_document(doc_id)
    if Path(file.filename or "").suffix.casefold() != ".docx":
        raise HTTPException(status_code=415, detail="Only .docx uploads are supported")
    payload = await file.read(MAX_UPLOAD_BYTES + 1)
    if not payload or len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload must be between 1 byte and 15 MiB")

    settings = get_settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    target = settings.uploads_dir / f"{doc_id}.docx"
    fd, temp_name = tempfile.mkstemp(prefix=f".{doc_id}_", suffix=".docx", dir=settings.uploads_dir)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
        try:
            count = await run_in_threadpool(_index_docx, temp_path, doc_id, entry["title"])
        except Exception as exc:
            logger.exception("admin_document_index_failed doc_id=%s", doc_id)
            raise HTTPException(status_code=422, detail="Document could not be parsed and indexed") from exc

        # Keep a source copy for operator review. The fixed manifest stays unchanged.
        os.replace(temp_path, target)
        deleted_ids = _read_deleted_ids()
        if doc_id in deleted_ids:
            deleted_ids.remove(doc_id)
            _write_deleted_ids(deleted_ids)
        try:
            get_retrieval_service().refresh_bm25_index()
        except Exception:
            logger.exception("admin_document_bm25_refresh_failed doc_id=%s", doc_id)
            raise HTTPException(status_code=500, detail="Indexed document, but lexical index refresh failed")
        return {"doc_id": doc_id, "indexed_chunks": count, "source_file": target.name, "status": "replaced"}
    except HTTPException:
        raise
    finally:
        temp_path.unlink(missing_ok=True)


@router.delete("/admin/documents/{doc_id}")
async def delete_document(doc_id: str) -> dict[str, object]:
    """Remove a known starter document from the active vector and lexical indexes."""
    _manifest_document(doc_id)
    deleted_ids = _read_deleted_ids()
    deleted_ids.add(doc_id)
    _write_deleted_ids(deleted_ids)
    try:
        deleted = await run_in_threadpool(ChromaStore().delete_document, doc_id)
        override = get_settings().uploads_dir / f"{doc_id}.docx"
        override.unlink(missing_ok=True)
        get_retrieval_service().refresh_bm25_index()
    except Exception as exc:
        deleted_ids.discard(doc_id)
        _write_deleted_ids(deleted_ids)
        logger.exception("admin_document_delete_failed doc_id=%s", doc_id)
        raise HTTPException(status_code=500, detail="Document removal failed") from exc
    return {"doc_id": doc_id, "deleted_chunks": deleted, "status": "deleted"}
