"""Local demonstration analytics derived from completed chat records."""

from fastapi import APIRouter, HTTPException, Query

from app.storage.database import SQLiteStore

router = APIRouter()


@router.get("/admin/analytics")
def get_analytics(limit: int = Query(default=10, ge=1, le=100)) -> dict:
    """Return aggregate usage, top synthetic questions, abstentions, tokens and latency."""
    return SQLiteStore().analytics(limit=limit)


@router.get("/admin/analytics/sessions/{session_id}")
def get_session_metrics(session_id: str) -> dict:
    """Expose token and latency counters for a single evaluation/demo session."""
    record = SQLiteStore().conversation_metrics(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No conversation metrics for this session")
    return record
