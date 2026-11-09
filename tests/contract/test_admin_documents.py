from fastapi.testclient import TestClient

from app.main import app


def test_document_upload_rejects_non_docx_before_indexing():
    response = TestClient(app).post(
        "/admin/documents",
        data={"doc_id": "KB-01"},
        files={"file": ("source.txt", b"synthetic test payload", "text/plain")},
    )
    assert response.status_code == 415
    assert response.json()["detail"] == "Only .docx uploads are supported"


def test_document_delete_rejects_unknown_id_without_touching_index():
    response = TestClient(app).delete("/admin/documents/KB-99")
    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown starter corpus document ID"
