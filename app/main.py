"""FastAPI application factory."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router
from app.api.analytics import router as analytics_router
from app.api.admin_documents import router as admin_documents_router
from app.api.health import router as health_router
from app.api.handoff import router as handoff_router
from app.core.config import get_settings, validate_storage_paths


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))
    validate_storage_paths(settings)
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

    return application


app = create_app()
