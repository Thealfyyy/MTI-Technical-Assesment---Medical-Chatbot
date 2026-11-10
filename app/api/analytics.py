"""Local demonstration analytics derived from completed chat records."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import require_admin
from app.storage.database import SQLiteStore

router = APIRouter()


@router.get("/admin/analytics", dependencies=[Depends(require_admin)])
def get_analytics(limit: int = Query(default=10, ge=1, le=100)) -> dict[str, Any]:
    """Return aggregate usage, top synthetic questions, abstentions, tokens and latency."""
    return SQLiteStore().analytics(limit=limit)


@router.post("/admin/analytics/reset", dependencies=[Depends(require_admin)])
def reset_analytics() -> dict[str, Any]:
    """Zero out conversation analytics records while preserving escalation handoffs."""
    deleted = SQLiteStore().clear_analytics()
    return {"message": "Operational analytics reset successfully.", "deleted_records": deleted}


@router.get("/admin/analytics/sessions/{session_id}")
def get_session_metrics(session_id: str) -> dict[str, Any]:
    """Expose token and latency counters for a single evaluation/demo session."""
    record = SQLiteStore().conversation_metrics(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No conversation metrics for this session")
    return record
