from fastapi.testclient import TestClient

from app.main import app


def test_document_upload_rejects_non_docx_before_indexing():
    response = TestClient(app).post(
        "/admin/documents",
        data={"doc_id": "KB-01"},
        files={"file": ("source.txt", b"synthetic test payload", "text/plain")},
        auth=("admin", "admin123"),
    )
    assert response.status_code == 415
    assert response.json()["detail"] == "Only .docx uploads are supported"


def test_document_delete_rejects_unknown_id_without_touching_index():
    response = TestClient(app).delete("/admin/documents/KB-99", auth=("admin", "admin123"))
    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown starter corpus document ID"


def test_list_documents_returns_catalog():
    response = TestClient(app).get("/admin/documents", auth=("admin", "admin123"))
    assert response.status_code == 200
    docs = response.json()
    assert isinstance(docs, list)
    assert len(docs) >= 9
    kb_ids = {d["doc_id"] for d in docs}
    assert "KB-01" in kb_ids
    assert "KB-06" in kb_ids
    for d in docs:
        assert "doc_id" in d
        assert "title" in d
        assert "chunks_count" in d
        assert "status" in d


def test_document_upload_rejects_empty_doc_id():
    response = TestClient(app).post(
        "/admin/documents",
        data={"doc_id": "   "},
        files={"file": ("sample.docx", b"PK\x03\x04", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        auth=("admin", "admin123"),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Document ID is required"
