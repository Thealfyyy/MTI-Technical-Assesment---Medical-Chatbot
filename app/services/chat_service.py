"""Safety-first orchestration for retrieval, grounded generation, and citations."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass

from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.generation.grounding import check_answer_grounding
from app.generation.llm_client import LLMClient
from app.retrieval.service import RetrievalService, get_retrieval_service
from app.safety.guards import (
    SafetyOutcome,
    classify_safety,
    detect_answer_language,
    response_language_for_query,
    static_reply_language,
)
from app.schemas.api import ChatResponse
from app.schemas.chunk import RetrievedChunk

logger = logging.getLogger(__name__)

SNIPPET_LIMIT = 280


@dataclass
class ChatExecution:
    response: ChatResponse
    session_id: str
    latency_ms: float
    retrieval_ms: float
    generation_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    retrieved_chunks: list[RetrievedChunk]


def _safe_abstention(language: str) -> str:
    if language == "ar":
        return "لا أجد في المصادر المعتمدة معلومات كافية للإجابة عن هذا السؤال."
    if language == "mixed":
        return "لا أجد في المصادر المعتمدة supporting evidence كافياً للإجابة عن هذا السؤال."
    return "I could not find enough supporting information in the approved sources to answer this question."


def _safe_escalation(language: str) -> str:
    if language == "ar":
        return "قد تتطلب الحالة تقييماً عاجلاً من مختص. يُرجى التواصل مع خدمات الطوارئ المحلية أو مختص صحي فوراً."
    if language == "mixed":
        return "قد تتطلب الحالة تقييماً عاجلاً من مختص. Please contact local emergency services or a qualified clinician now."
    return "This may require urgent professional assessment. Please contact local emergency services or a qualified clinician now."


class ChatService:
    """Coordinates the deterministic safety gate with retrieval and grounded generation."""

    def __init__(self, retriever: RetrievalService | None = None, llm: LLMClient | None = None) -> None:
        self.settings = get_settings()
        self.retriever = retriever or get_retrieval_service()
        self.llm = llm or LLMClient()

    async def process(self, message: str, session_id: str | None = None) -> ChatExecution:
        started = time.perf_counter()
        session = session_id or uuid.uuid4().hex
        language = response_language_for_query(message)
        # The fixed replies are returned as-is, so their label follows the reply
        # script rather than the generation hint for the model.
        reply_language = static_reply_language(message)

        # 1. Red flag acute medical emergencies never reach retrieval/LLM.
        from app.safety.guards import is_emergency, is_personal_dose, is_disease_symptom_query
        from app.generation.grounding import contains_off_corpus_substance

        if is_emergency(message):
            response = ChatResponse(
                answer=_safe_escalation(reply_language), citations=[], status="escalated", language=reply_language
            )
            return ChatExecution(response, session, (time.perf_counter() - started) * 1000, 0, 0, None, None, [])

        # 2. Disease/illness diagnostic symptoms and absent drugs are out of formulary scope.
        if is_disease_symptom_query(message) or contains_off_corpus_substance(message):
            response = ChatResponse(
                answer=_safe_abstention(reply_language), citations=[], status="out_of_scope", language=reply_language
            )
            return ChatExecution(response, session, (time.perf_counter() - started) * 1000, 0, 0, None, None, [])

        # 3. Patient-specific dose questions on formulary drugs require professional assessment.
        if is_personal_dose(message):
            response = ChatResponse(
                answer=_safe_escalation(reply_language), citations=[], status="escalated", language=reply_language
            )
            return ChatExecution(response, session, (time.perf_counter() - started) * 1000, 0, 0, None, None, [])

        retrieval_started = time.perf_counter()
        chunks = await run_in_threadpool(
            self.retriever.retrieve,
            message,
            self.settings.retrieval_top_k,
            True,
            self.settings.retrieval_min_score,
        )
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
        if not chunks:
            response = ChatResponse(
                answer=_safe_abstention(reply_language), citations=[], status="out_of_scope", language=reply_language
            )
            return ChatExecution(response, session, (time.perf_counter() - started) * 1000, retrieval_ms, 0, None, None, [])

        generation_started = time.perf_counter()
        generated = await self.llm.generate_grounded_answer(message, chunks, language)
        generation_ms = (time.perf_counter() - generation_started) * 1000

        if generated.escalate:
            # The model may escalate patient-specific advice that the regex guard does not match.
            response = ChatResponse(
                answer=_safe_escalation(reply_language), citations=[], status="escalated", language=reply_language
            )
            return ChatExecution(
                response, session, (time.perf_counter() - started) * 1000, retrieval_ms, generation_ms,
                generated.prompt_tokens, generated.completion_tokens, chunks,
            )

        if generated.insufficient or not generated.answer or not generated.evidence:
            response = ChatResponse(
                answer=_safe_abstention(reply_language), citations=[], status="out_of_scope", language=reply_language
            )
            return ChatExecution(
                response, session, (time.perf_counter() - started) * 1000, retrieval_ms, generation_ms,
                generated.prompt_tokens, generated.completion_tokens, chunks,
            )

        by_id = {chunk.chunk_id: chunk for chunk in chunks}
        citations: list[dict[str, str]] = []
        seen_doc_sections: set[tuple[str, str]] = set()
        quoted_parts: list[str] = []
        cited_text: list[str] = []
        for chunk_id, quote in generated.evidence:
            chunk = by_id[chunk_id]
            quoted_parts.append(quote)
            cited_text.append(f"{chunk.chunk_id} {chunk.doc_id} {chunk.text}")
            citation = {**chunk.to_citation_dict(), "snippet": quote[:SNIPPET_LIMIT]}
            citation_key = (citation["doc_id"], citation["section"])
            if citation_key not in seen_doc_sections:
                seen_doc_sections.add(citation_key)
                citations.append(citation)

        answer = generated.answer.strip()
        grounding = check_answer_grounding(answer, " ".join(cited_text), message)
        if not grounding.ok:
            # The composed prose mentions something its sources do not contain;
            # fall back to the verified spans rather than returning ungrounded text.
            logger.info("grounding_fallback unsupported_term_count=%d unsupported=%s", len(grounding.unsupported), grounding.unsupported)
            answer = "\n\n".join(quoted_parts)

        response = ChatResponse(
            answer=answer,
            citations=citations,
            status="answered",
            language=detect_answer_language(answer),
        )
        return ChatExecution(
            response, session, (time.perf_counter() - started) * 1000, retrieval_ms, generation_ms,
            generated.prompt_tokens, generated.completion_tokens, chunks,
        )


_CHAT_SERVICE: ChatService | None = None


def get_chat_service() -> ChatService:
    global _CHAT_SERVICE
    if _CHAT_SERVICE is None:
        _CHAT_SERVICE = ChatService()
    return _CHAT_SERVICE


def reset_chat_service_for_tests() -> None:
    global _CHAT_SERVICE
    _CHAT_SERVICE = None
