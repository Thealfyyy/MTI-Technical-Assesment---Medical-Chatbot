"""Chat endpoint with exact response shape and bounded execution time."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.schemas.api import ChatRequest, ChatResponse
from app.services.chat_service import get_chat_service
from app.storage.database import SQLiteStore

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse | JSONResponse:
    """Answer from approved KB excerpts, abstain, or escalate safety-critical input."""
    settings = get_settings()
    try:
        async def _handle_request():
            service = await run_in_threadpool(get_chat_service)
            return await service.process(request.message, request.session_id)

        execution = await asyncio.wait_for(_handle_request(), timeout=settings.request_timeout_seconds)
        logger.info(
            "chat_completed status=%s language=%s duration_ms=%.1f retrieval_ms=%.1f generation_ms=%.1f",
            execution.response.status,
            execution.response.language,
            execution.latency_ms,
            execution.retrieval_ms,
            execution.generation_ms,
        )
        try:
            SQLiteStore().record_conversation(
                session_id=execution.session_id,
                question=request.message,
                status=execution.response.status,
                language=execution.response.language,
                model=settings.llm_model_name,
                prompt_tokens=execution.prompt_tokens,
                completion_tokens=execution.completion_tokens,
                retrieval_ms=execution.retrieval_ms,
                generation_ms=execution.generation_ms,
                total_ms=execution.latency_ms,
            )
        except Exception:
            # Analytics persistence must not turn a valid answer into an API failure.
            logger.exception("chat_analytics_persistence_failed")
        return execution.response
    except (TimeoutError, asyncio.TimeoutError):
        logger.warning("chat_timeout timeout_seconds=%.1f", settings.request_timeout_seconds)
        return JSONResponse(status_code=500, content={"error": "Request timed out"})
    except Exception:
        # Never log user message text, prompt contents, or model output.
        logger.exception("chat_failed")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})
