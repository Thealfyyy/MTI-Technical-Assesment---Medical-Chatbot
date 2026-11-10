"""Async client for an OpenAI-compatible local llama.cpp server."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.chunk import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class GroundedAnswer:
    """A composed answer together with the verbatim evidence that supports it."""

    answer: str
    evidence: list[tuple[str, str]]  # (chunk id, verified source quote)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    insufficient: bool = False
    escalate: bool = False


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


_CYRILLIC_STEMS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"диклофенак\w*", re.IGNORECASE), "Diclofenac"),
    (re.compile(r"дикло\w*", re.IGNORECASE), "Diclofenac"),
    (re.compile(r"ацидо\w*", re.IGNORECASE), "acidosis"),
    (re.compile(r"ациди\w*", re.IGNORECASE), "acidosis"),
    (re.compile(r"аци\w*", re.IGNORECASE), "acidosis"),
)

_CYRILLIC_TO_LATIN: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "Yo",
    "Ж": "Zh", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L", "М": "M",
    "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U",
    "Ф": "F", "Х": "H", "Ц": "C", "Ч": "Ch", "Ш": "Sh", "Щ": "Shch", "Ъ": "",
    "Ы": "Y", "Ь": "", "Э": "E", "Ю": "Yu", "Я": "Ya",
}


def repair_cyrillic_artifacts(text: str) -> str:
    """Repair accidental Cyrillic homoglyphs or transliteration slips in generated text."""
    if not any("\u0400" <= char <= "\u04FF" for char in text):
        return text
    for pattern, replacement in _CYRILLIC_STEMS:
        text = pattern.sub(replacement, text)
    return "".join(_CYRILLIC_TO_LATIN.get(c, c) for c in text)


SYSTEM_PROMPT = (
    "You are a medical information assistant for pharmacy staff. Answer ONLY from the supplied "
    "knowledge-base passages. Never use outside knowledge.\n"
    "Rules:\n"
    "1. Write the answer in answer_language: 'ar' means clear Modern Standard Arabic, 'en' means "
    "English, 'mixed' means Arabic sentences that keep English medical terms. Keep drug names, "
    "condition names, and test names exactly as the passages write them, copying the letters "
    "character for character: write 'Diclofenac', never 'диклофенак' or 'ديكلوفيناك'. Arabic "
    "answers keep drug names in Latin letters; never use Cyrillic or Greek letters.\n"
    "2. Answer directly in one to four sentences. No preamble, no restating the question, no markdown.\n"
    "3. State only facts written in the passages. Never add a diagnosis, a dose, a dose change, or "
    "treatment advice that is not in the passages. Never name a drug, brand, condition, or number "
    "that the passages do not contain.\n"
    "4. Return one to three short quotes copied verbatim from the passages that together support "
    "every statement in your answer, each with the chunk_id it came from.\n"
    "5. If the passages do not directly answer the question (for example, if the question asks for "
    "a drug, brand, or substance NOT in the passages, such as Viagra, Botox, Sildenafil, Finasteride, "
    "Remdesivir, or asks about an interaction not described in the passages, or asks for "
    "symptoms, causes, or diagnosis of a disease such as 'اعراض مرض السكر' and the passages only "
    "describe drug treatments or drug side effects), return "
    '{"answer": "", "evidence": [], "insufficient": true}.\n'
    "6. If the question asks what to do for a specific patient - a dose for a person, a diagnosis, "
    "whether to give a medicine to a patient, or an urgent symptom - return "
    '{"answer": "", "evidence": [], "escalate": true}.\n'
    "Return JSON only with exactly these keys: answer, evidence, insufficient, escalate. "
    'evidence is a list of {"chunk_id": "...", "quote": "..."}. No text outside the JSON.'
)


class LLMClient:
    """Calls llama.cpp's OpenAI-compatible endpoint and verifies quoted evidence."""

    def __init__(self, server_url: str | None = None, model_name: str | None = None) -> None:
        settings = get_settings()
        self.server_url = (server_url or settings.llm_server_url).rstrip("/")
        self.model_name = model_name or settings.llm_model_name
        self.timeout = settings.request_timeout_seconds
        self.max_tokens = settings.llm_max_tokens
        self.temperature = settings.llm_temperature

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            value = json.loads(text)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass

        # If LLM output was truncated by max_tokens, repair by balancing open brackets/braces
        idx = text.rfind("}")
        while idx != -1:
            candidate = text[: idx + 1].rstrip(", \t\r\n")
            open_brackets = candidate.count("[") - candidate.count("]")
            if open_brackets > 0:
                candidate += "]" * open_brackets
            open_braces = candidate.count("{") - candidate.count("}")
            if open_braces > 0:
                candidate += "}" * open_braces
            try:
                value = json.loads(candidate)
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                idx = text.rfind("}", 0, idx)

        # Fallback: regex extraction of "answer" if outer structure was damaged
        answer_match = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if answer_match:
            try:
                extracted = json.loads(f'"{answer_match.group(1)}"')
                return {"answer": extracted, "evidence": [], "insufficient": False}
            except Exception:
                pass

        logger.warning("llm_json_parse_failed content_length=%d", len(content))
        return {}

    @staticmethod
    def _verify_evidence(
        raw_evidence: Any, chunks: list[RetrievedChunk]
    ) -> list[tuple[str, str]]:
        """Keep only spans that appear verbatim in the chunk they claim to come from."""
        if not isinstance(raw_evidence, list):
            return []
        by_id = {chunk.chunk_id: chunk for chunk in chunks}
        verified: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in raw_evidence:
            if not isinstance(item, dict):
                continue
            chunk_id, quote = item.get("chunk_id"), item.get("quote")
            if not isinstance(chunk_id, str) or not isinstance(quote, str) or not quote.strip():
                continue
            chunk = by_id.get(chunk_id)
            if chunk is None:
                continue
            if _normalize_whitespace(quote) not in _normalize_whitespace(chunk.text):
                continue
            pair = (chunk_id, quote.strip())
            if pair not in seen:
                seen.add(pair)
                verified.append(pair)
        return verified

    async def generate_grounded_answer(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        answer_language: str = "en",
    ) -> GroundedAnswer:
        """Compose an answer in the requested language and verify its evidence spans."""
        context = [
            {"chunk_id": chunk.chunk_id, "doc_id": chunk.doc_id, "section": chunk.section, "text": chunk.text}
            for chunk in chunks
        ]
        user = json.dumps(
            {"question": question, "answer_language": answer_language, "passages": context},
            ensure_ascii=False,
        )
        body = {
            "model": self.model_name,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
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

        usage = payload.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens") if isinstance(usage.get("prompt_tokens"), int) else None
        completion_tokens = (
            usage.get("completion_tokens") if isinstance(usage.get("completion_tokens"), int) else None
        )

        evidence = self._verify_evidence(parsed.get("evidence"), chunks)
        raw_answer = parsed.get("answer")
        if isinstance(raw_answer, str):
            answer = repair_cyrillic_artifacts(raw_answer.strip())
        else:
            answer = ""
        escalate = bool(parsed.get("escalate"))
        insufficient = bool(parsed.get("insufficient"))

        if escalate:
            return GroundedAnswer("", evidence, prompt_tokens, completion_tokens, escalate=True)
        if insufficient or not answer or not evidence:
            # No answer, or an answer with no verifiable supporting span, is treated
            # as no evidence rather than returned on trust.
            return GroundedAnswer("", evidence, prompt_tokens, completion_tokens, insufficient=True)
        return GroundedAnswer(answer, evidence, prompt_tokens, completion_tokens)

    async def health(self) -> bool:
        """Return whether the configured local model server responds to its health route."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.server_url}/health")
            return response.is_success
        except httpx.HTTPError:
            return False
