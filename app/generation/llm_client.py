"""Async client for an OpenAI-compatible local llama.cpp server."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.chunk import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class ExtractiveAnswer:
    """A model-selected set of verbatim evidence excerpts."""

    quotes: list[tuple[str, str]]  # (chunk id, exact source quote)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class LLMClient:
    """Calls llama.cpp's OpenAI-compatible endpoint and validates source quotes."""

    def __init__(self, server_url: str | None = None, model_name: str | None = None) -> None:
        settings = get_settings()
        self.server_url = (server_url or settings.llm_server_url).rstrip("/")
        self.model_name = model_name or settings.llm_model_name
        self.timeout = settings.request_timeout_seconds
        self.max_tokens = settings.llm_max_tokens
        self.temperature = settings.llm_temperature

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        value = json.loads(content.strip())
        if not isinstance(value, dict):
            raise ValueError("Model response must be a JSON object")
        return value

    async def extract_supported_quotes(self, question: str, chunks: list[RetrievedChunk]) -> ExtractiveAnswer:
        """Ask the model to select only verbatim spans, then verify every span locally."""
        context = [
            {"chunk_id": chunk.chunk_id, "doc_id": chunk.doc_id, "section": chunk.section, "text": chunk.text}
            for chunk in chunks
        ]
        system = (
            "You are an extractive assistant for a pharmacy knowledge base. Use ONLY the supplied passages. "
            "Do not use prior knowledge, infer missing facts, recommend a diagnosis, or add a dose/treatment. "
            "Return JSON only with exactly this shape: {\"evidence\":[{\"chunk_id\":\"...\",\"quote\":\"...\"}]}. "
            "Each quote must be copied verbatim from the text of its named chunk. Select the shortest complete "
            "passage spans that answer the question. If the passages do not directly support an answer, return "
            "{\"evidence\":[]}. Do not include explanations outside the JSON."
        )
        user = json.dumps({"question": question, "passages": context}, ensure_ascii=False)
        body = {
            "model": self.model_name,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.server_url}/v1/chat/completions", json=body)
            response.raise_for_status()
            payload = response.json()

        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("LLM returned no completion choices")
        content = choices[0].get("message", {}).get("content", "")
        parsed = self._parse_json(content)
        evidence = parsed.get("evidence")
        if not isinstance(evidence, list):
            raise ValueError("LLM JSON is missing the evidence list")

        by_id = {chunk.chunk_id: chunk for chunk in chunks}
        quotes: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in evidence:
            if not isinstance(item, dict):
                continue
            chunk_id, quote = item.get("chunk_id"), item.get("quote")
            if not isinstance(chunk_id, str) or not isinstance(quote, str) or not quote.strip():
                continue
            chunk = by_id.get(chunk_id)
            if chunk is None:
                continue
            # Exact normalized whitespace match prevents fabricated source spans.
            normalize = lambda value: " ".join(value.split())
            if normalize(quote) not in normalize(chunk.text):
                continue
            pair = (chunk_id, quote.strip())
            if pair not in seen:
                seen.add(pair)
                quotes.append(pair)

        usage = payload.get("usage") or {}
        return ExtractiveAnswer(
            quotes=quotes,
            prompt_tokens=usage.get("prompt_tokens") if isinstance(usage.get("prompt_tokens"), int) else None,
            completion_tokens=usage.get("completion_tokens") if isinstance(usage.get("completion_tokens"), int) else None,
        )

    async def health(self) -> bool:
        """Return whether the configured local model server responds to its health route."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.server_url}/health")
            return response.is_success
        except httpx.HTTPError:
            return False
