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
    return _get_document(doc_id)


def _custom_docs_path() -> Path:
    return get_settings().uploads_dir / "custom_documents.json"


def _read_custom_docs() -> dict[str, dict]:
    path = _custom_docs_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {item["doc_id"]: item for item in data} if isinstance(data, list) else data
    except Exception:
        return {}


def _write_custom_docs(docs: dict[str, dict]) -> None:
    path = _custom_docs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(list(docs.values()), stream, indent=2, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _get_document(doc_id: str) -> dict:
    settings = get_settings()
    manifest = yaml.safe_load(settings.kb_manifest_path.read_text(encoding="utf-8"))
    for item in manifest.get("documents", []):
        if item.get("doc_id") == doc_id:
            return item
    custom_docs = _read_custom_docs()
    if doc_id in custom_docs:
        return custom_docs[doc_id]
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
    custom_docs = _read_custom_docs()
    store = ChromaStore()
    all_chunks = store.get_all_chunks()
    chunk_counts = Counter(c.metadata.doc_id for c in all_chunks)

    # Union of manifest docs and custom docs
    docs_map: dict[str, dict] = {}
    for item in manifest.get("documents", []):
        docs_map[item["doc_id"]] = {
            "doc_id": item["doc_id"],
            "title": item.get("title", item["doc_id"]),
            "category": item.get("category", "General"),
            "source_file": item.get("source_file", ""),
            "is_custom": False,
        }
    for doc_id, item in custom_docs.items():
        docs_map[doc_id] = {
            "doc_id": doc_id,
            "title": item.get("title", doc_id),
            "category": item.get("category", "Clinical Guideline"),
            "source_file": item.get("source_file", ""),
            "is_custom": True,
        }

    docs: list[dict[str, object]] = []
    for doc_id, item in docs_map.items():
        is_deleted = doc_id in deleted_ids
        override_file = settings.uploads_dir / f"{doc_id}.docx"
        is_replaced = (override_file.is_file() and not is_deleted) or item.get("is_custom", False)

        status = "deleted" if is_deleted else ("custom" if item.get("is_custom") else ("replaced" if is_replaced else "active"))
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
async def replace_document(
    doc_id: str = Form(...),
    title: str | None = Form(None),
    category: str | None = Form(None),
    file: UploadFile = File(...)
) -> dict[str, object]:
    """Upload a new or replacement KB document and re-index it before committing the upload."""
    doc_id = doc_id.strip()
    if not doc_id:
        raise HTTPException(status_code=400, detail="Document ID is required")

    settings = get_settings()
    custom_docs = _read_custom_docs()

    # Determine title and category
    existing_meta: dict | None = None
    try:
        existing_meta = _get_document(doc_id)
    except HTTPException:
        existing_meta = None

    if existing_meta:
        doc_title = title.strip() if title and title.strip() else existing_meta.get("title", doc_id)
        doc_category = category.strip() if category and category.strip() else existing_meta.get("category", "General")
    else:
        doc_title = title.strip() if title and title.strip() else (Path(file.filename or "").stem or doc_id)
        doc_category = category.strip() if category and category.strip() else "Clinical Guideline"

    if Path(file.filename or "").suffix.casefold() != ".docx":
        raise HTTPException(status_code=415, detail="Only .docx uploads are supported")
    payload = await file.read(MAX_UPLOAD_BYTES + 1)
    if not payload or len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload must be between 1 byte and 15 MiB")

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    target = settings.uploads_dir / f"{doc_id}.docx"
    fd, temp_name = tempfile.mkstemp(prefix=f".{doc_id}_", suffix=".docx", dir=settings.uploads_dir)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
        try:
            count = await run_in_threadpool(_index_docx, temp_path, doc_id, doc_title)
        except Exception as exc:
            logger.exception("admin_document_index_failed doc_id=%s", doc_id)
            raise HTTPException(status_code=422, detail="Document could not be parsed and indexed") from exc

        # Keep a source copy for operator review.
        os.replace(temp_path, target)

        # If it's a new custom document (not in manifest), persist in custom_documents.json
        manifest_docs = {
            item["doc_id"]
            for item in yaml.safe_load(settings.kb_manifest_path.read_text(encoding="utf-8")).get("documents", [])
        }
        if doc_id not in manifest_docs:
            custom_docs[doc_id] = {
                "doc_id": doc_id,
                "title": doc_title,
                "category": doc_category,
                "source_file": file.filename or target.name,
            }
            _write_custom_docs(custom_docs)

        deleted_ids = _read_deleted_ids()
        if doc_id in deleted_ids:
            deleted_ids.remove(doc_id)
            _write_deleted_ids(deleted_ids)
        try:
            get_retrieval_service().refresh_bm25_index()
        except Exception:
            logger.exception("admin_document_bm25_refresh_failed doc_id=%s", doc_id)
            raise HTTPException(status_code=500, detail="Indexed document, but lexical index refresh failed")
        return {"doc_id": doc_id, "title": doc_title, "indexed_chunks": count, "source_file": target.name, "status": "active"}
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
