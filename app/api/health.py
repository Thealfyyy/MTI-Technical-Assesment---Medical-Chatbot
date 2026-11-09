"""Readiness endpoint for the API and configured local model service."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.generation.llm_client import LLMClient
from app.schemas.api import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    if not await LLMClient().health():
        raise HTTPException(status_code=503, detail="Configured LLM server is not ready")
    return HealthResponse(llm=settings.llm_model_name, embedding=settings.embedding_model_name)
