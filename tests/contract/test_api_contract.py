from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.api import ChatResponse
from app.services.chat_service import ChatExecution


def test_chat_success_has_exact_top_level_fields():
    execution = ChatExecution(
        response=ChatResponse(answer="source quote", citations=[], status="out_of_scope", language="en"),
        session_id="session-1", latency_ms=1.0, retrieval_ms=0.5, generation_ms=0.0,
        prompt_tokens=None, completion_tokens=None, retrieved_chunks=[],
    )
    service = MagicMock()
    service.process = AsyncMock(return_value=execution)
    with patch("app.api.chat.get_chat_service", return_value=service):
        response = TestClient(app).post("/chat", json={"message": "Question", "session_id": "session-1"})
    assert response.status_code == 200
    assert set(response.json()) == {"answer", "citations", "status", "language"}


def test_chat_rejects_unknown_request_fields():
    response = TestClient(app).post("/chat", json={"message": "Question", "unexpected": True})
    assert response.status_code == 422


def test_chat_failure_uses_exact_500_error_shape():
    service = MagicMock()
    service.process = AsyncMock(side_effect=RuntimeError("private error"))
    with patch("app.api.chat.get_chat_service", return_value=service):
        response = TestClient(app).post("/chat", json={"message": "Question"})
    assert response.status_code == 500
    assert set(response.json()) == {"error"}


def test_health_contract_reports_configured_model_names():
    with patch("app.api.health.LLMClient.health", new=AsyncMock(return_value=True)):
        response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert set(response.json()) == {"status", "llm", "embedding"}
    assert response.json()["status"] == "ok"
