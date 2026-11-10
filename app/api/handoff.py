"""Demo-only escalation handoff capture endpoint."""

from fastapi import APIRouter, Body, Depends, HTTPException

from app.core.auth import require_admin
from app.schemas.api import HandoffRequest, HandoffResponse
from app.storage.database import SQLiteStore

router = APIRouter()


@router.post("/handoff", response_model=HandoffResponse, status_code=201)
def submit_handoff(request: HandoffRequest) -> HandoffResponse:
    handoff_id = SQLiteStore().save_handoff(
        session_id=request.session_id,
        summary=request.summary.strip(),
        contact_name=request.contact_name.strip(),
        contact_method=request.contact_method.strip(),
    )
    return HandoffResponse(
        accepted=True,
        handoff_id=handoff_id,
        message="Handoff details stored for this demonstration. No clinician has been contacted.",
    )


@router.get("/admin/handoffs", dependencies=[Depends(require_admin)])
def list_handoffs(limit: int = 50) -> list[dict]:
    """Return recent escalation handoff capture records for administrator review."""
    return SQLiteStore().list_handoffs(limit=limit)


@router.patch("/admin/handoffs/{handoff_id}", dependencies=[Depends(require_admin)])
def update_handoff(handoff_id: int, payload: dict = Body(...)) -> dict:
    """Update status of an escalation handoff record ('handled' or 'pending')."""
    new_status = payload.get("status", "handled")
    updated = SQLiteStore().update_handoff_status(handoff_id, new_status)
    if not updated:
        raise HTTPException(status_code=404, detail="Handoff record not found")
    return {"status": "ok", "handoff_id": handoff_id, "new_status": new_status}


@router.delete("/admin/handoffs/{handoff_id}", dependencies=[Depends(require_admin)])
def delete_handoff(handoff_id: int) -> dict:
    """Delete an escalation handoff record."""
    deleted = SQLiteStore().delete_handoff(handoff_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Handoff record not found")
    return {"status": "ok", "message": f"Handoff #{handoff_id} deleted successfully"}
