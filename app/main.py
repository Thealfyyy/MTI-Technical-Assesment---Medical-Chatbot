"""FastAPI application factory."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.api.chat import router as chat_router
from app.api.analytics import router as analytics_router
from app.api.admin_documents import router as admin_documents_router
from app.api.health import router as health_router
from app.api.handoff import router as handoff_router
from app.core.auth import require_admin, verify_admin_token
from app.core.config import get_settings, validate_storage_paths


def _warm_retrieval() -> None:
    """Load the embedding model and BM25 index before the first user request.

    Both are built lazily; on a cold start the first retrieval paid a ~25 s
    model load, which sits right against the request budget and can turn the
    first question into a timeout. Serving the cost at startup keeps every
    request inside the latency target.
    """
    from app.retrieval.service import get_retrieval_service

    service = get_retrieval_service()
    service.get_bm25_index()
    service.embedder.embed_query("warmup")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))
    validate_storage_paths(settings)
    if os.getenv("WARMUP_ON_STARTUP", "1") != "0":
        await run_in_threadpool(_warm_retrieval)
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="MTI Medical Knowledge Chatbot", version="0.1.0", lifespan=lifespan)
    application.include_router(chat_router)
    application.include_router(health_router)
    application.include_router(handoff_router)
    application.include_router(analytics_router)
    application.include_router(admin_documents_router)
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    application.mount("/static", StaticFiles(directory=static_dir), name="static")

    @application.get("/", include_in_schema=False)
    async def index():
        return FileResponse(os.path.join(static_dir, "index.html"))

    @application.get("/admin", include_in_schema=False)
    async def admin():
        return FileResponse(os.path.join(static_dir, "admin.html"))

    @application.post("/admin/auth/verify", include_in_schema=False)
    async def verify_auth_token(payload: dict[str, str] = Body(default={})):
        token = payload.get("token", "") or payload.get("secret", "")
        if verify_admin_token(token):
            return {"status": "ok", "message": "Token verified successfully"}
        raise HTTPException(status_code=401, detail="Invalid admin token secret")

    return application


app = create_app()
