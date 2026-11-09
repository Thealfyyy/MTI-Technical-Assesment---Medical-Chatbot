"""HTTP request and response contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=8000)


class Citation(BaseModel):
    doc_id: str
    title: str
    section: str
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    status: Literal["answered", "out_of_scope", "escalated"]
    language: Literal["ar", "en", "mixed"]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    llm: str
    embedding: str


class HandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=128)
    summary: str = Field(min_length=1, max_length=1000)
    contact_name: str = Field(min_length=1, max_length=100)
    contact_method: str = Field(min_length=3, max_length=254)


class HandoffResponse(BaseModel):
    accepted: bool
    handoff_id: int
    message: str
