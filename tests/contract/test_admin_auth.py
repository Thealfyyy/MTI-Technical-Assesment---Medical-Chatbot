from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.storage.database import SQLiteStore


def test_admin_auth_bypass_when_disabled(monkeypatch):
    monkeypatch.setenv("ADMIN_AUTH_ENABLED", "false")
    get_settings.cache_clear()
    client = TestClient(app)
    response = client.get("/admin/analytics")
    assert response.status_code == 200


def test_admin_auth_enforced_when_enabled(monkeypatch):
    monkeypatch.setenv("ADMIN_AUTH_ENABLED", "true")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secretpass")
    get_settings.cache_clear()

    client = TestClient(app)

    # Missing credentials -> 401
    resp_unauth = client.get("/admin/analytics")
    assert resp_unauth.status_code == 401
    assert "Basic" in resp_unauth.headers.get("WWW-Authenticate", "")

    # Wrong credentials -> 401
    resp_bad = client.get("/admin/analytics", auth=("admin", "wrongpassword"))
    assert resp_bad.status_code == 401

    # Valid credentials -> 200
    resp_ok = client.get("/admin/analytics", auth=("admin", "secretpass"))
    assert resp_ok.status_code == 200


def test_admin_analytics_reset(monkeypatch):
    monkeypatch.setenv("ADMIN_AUTH_ENABLED", "false")
    get_settings.cache_clear()
    client = TestClient(app)

    store = SQLiteStore()
    store.record_conversation(
        session_id="test-reset",
        question="test reset question",
        status="answered",
        language="en",
        model="test",
        prompt_tokens=10,
        completion_tokens=5,
        retrieval_ms=1.0,
        generation_ms=2.0,
        total_ms=3.0,
    )

    response = client.post("/admin/analytics/reset")
    assert response.status_code == 200
    assert response.json()["message"] == "Operational analytics reset successfully."
    assert response.json()["deleted_records"] >= 1

    analytics = client.get("/admin/analytics").json()
    assert analytics["conversation_volume"] == 0
