"""Demo-only escalation handoff capture endpoint."""

from fastapi import APIRouter

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
