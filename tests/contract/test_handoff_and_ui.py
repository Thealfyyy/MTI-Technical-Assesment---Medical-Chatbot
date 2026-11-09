from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.storage.database import SQLiteStore


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        project_root=tmp_path, require_writable_storage=False, corpus_dir=tmp_path / "Docs/Data",
        kb_manifest_path=tmp_path / "manifest.yaml", chroma_persist_dir=tmp_path / "chroma",
        sqlite_db_path=tmp_path / "app.db", uploads_dir=tmp_path / "uploads",
        eval_results_dir=tmp_path / "results", model_cache_dir=tmp_path / "models",
        hf_home=tmp_path / "hf", sentence_transformers_home=tmp_path / "st",
        app_host="127.0.0.1", app_port=8000, request_timeout_seconds=28,
        llm_server_url="http://127.0.0.1:8080", llm_model_name="test-model",
        llm_max_tokens=100, llm_temperature=0.0, retrieval_top_k=3,
        retrieval_min_score=0.50, embedding_model_name="BAAI/bge-m3",
    )


def test_chat_page_and_static_assets_are_served():
    client = TestClient(app)
    page = client.get("/")
    script = client.get("/static/app.js")
    assert page.status_code == 200 and "chat-form" in page.text
    assert script.status_code == 200 and "textContent" in script.text


def test_handoff_is_saved_and_discloses_no_clinician_contact(tmp_path):
    with patch("app.storage.database.get_settings", return_value=_settings(tmp_path)):
        response = TestClient(app).post("/handoff", json={
            "session_id": "synthetic-session", "summary": "Synthetic demo escalation",
            "contact_name": "Test User", "contact_method": "test@example.invalid",
        })
        row = SQLiteStore(tmp_path / "app.db").analytics()
    assert response.status_code == 201
    assert response.json()["accepted"] is True
    assert "No clinician has been contacted" in response.json()["message"]
    assert row["conversation_volume"] == 0
