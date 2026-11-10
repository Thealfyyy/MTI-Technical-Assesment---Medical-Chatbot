from unittest.mock import AsyncMock, MagicMock

import pytest

from app.generation.llm_client import GroundedAnswer
from app.schemas.chunk import RetrievedChunk
from app.services.chat_service import ChatService


def _chunk(text="Cataflam contains Diclofenac potassium."):
    return RetrievedChunk(
        doc_id="KB-03", title="Pain & Fever", section="NSAIDs > Trade Names", chunk_id="KB-03-C001",
        snippet=text, text=text, score=0.8, rank=1, source="hybrid",
    )


def _service(chunks, generated):
    retriever = MagicMock()
    retriever.retrieve.return_value = chunks
    llm = MagicMock()
    llm.generate_grounded_answer = AsyncMock(return_value=generated)
    return ChatService(retriever=retriever, llm=llm), retriever, llm


@pytest.mark.asyncio
async def test_composed_answer_is_returned_with_verified_citation_snippet():
    service, _, _ = _service(
        [_chunk()],
        GroundedAnswer(
            answer="Cataflam contains Diclofenac potassium.",
            evidence=[("KB-03-C001", "Cataflam contains Diclofenac potassium.")],
            prompt_tokens=90,
            completion_tokens=20,
        ),
    )
    result = await service.process("What is Cataflam?")
    assert result.response.status == "answered"
    assert result.response.answer == "Cataflam contains Diclofenac potassium."
    assert result.response.citations[0].doc_id == "KB-03"
    assert result.response.citations[0].snippet == "Cataflam contains Diclofenac potassium."
    assert result.prompt_tokens == 90


@pytest.mark.asyncio
async def test_arabic_question_with_english_drug_name_gets_arabic_answer():
    service, _, llm = _service(
        [_chunk("Controloc – Pantoprazole. Proton Pump Inhibitors (PPIs)")],
        GroundedAnswer(
            answer="المادة الفعالة في Controloc هي Pantoprazole، وهو من مجموعة PPIs.",
            evidence=[("KB-03-C001", "Controloc – Pantoprazole")],
        ),
    )
    # Arabic prose with an English drug name: the model is told to write Arabic
    # sentences and keep English medical terms, and the label stays `ar`.
    result = await service.process("ايه المادة الفعالة في Controloc؟")
    assert result.response.status == "answered"
    assert result.response.language == "ar"
    assert result.response.answer.startswith("المادة الفعالة")
    assert llm.generate_grounded_answer.call_args.args[2] == "mixed"


@pytest.mark.asyncio
async def test_franco_question_requests_an_arabic_answer():
    service, _, llm = _service(
        [_chunk("Controloc – Pantoprazole")],
        GroundedAnswer(
            answer="المادة الفعالة في Controloc هي Pantoprazole.",
            evidence=[("KB-03-C001", "Controloc – Pantoprazole")],
        ),
    )
    result = await service.process("eh el mada el fa3ala fe Controloc?")
    assert result.response.status == "answered"
    assert result.response.language == "ar"
    assert llm.generate_grounded_answer.call_args.args[2] == "ar"


@pytest.mark.asyncio
async def test_unsupported_number_falls_back_to_verified_quote():
    service, _, _ = _service(
        [_chunk("Diclofenac potassium 50 mg tablets.")],
        GroundedAnswer(
            answer="Take 500 mg of Diclofenac potassium daily.",
            evidence=[("KB-03-C001", "Diclofenac potassium 50 mg tablets.")],
        ),
    )
    result = await service.process("What is Cataflam?")
    assert result.response.status == "answered"
    assert result.response.answer == "Diclofenac potassium 50 mg tablets."
    assert result.response.citations[0].snippet == "Diclofenac potassium 50 mg tablets."


@pytest.mark.asyncio
async def test_unsupported_drug_name_falls_back_to_verified_quote():
    service, _, _ = _service(
        [_chunk("Cataflam contains Diclofenac potassium.")],
        GroundedAnswer(
            answer="Cataflam is an alternative to Aspirin.",
            evidence=[("KB-03-C001", "Cataflam contains Diclofenac potassium.")],
        ),
    )
    result = await service.process("What is Cataflam?")
    assert result.response.status == "answered"
    assert result.response.answer == "Cataflam contains Diclofenac potassium."


@pytest.mark.asyncio
async def test_empty_retrieval_abstains_without_calling_llm():
    service, retriever, llm = _service([], GroundedAnswer(answer="", evidence=[]))
    result = await service.process("Question outside the corpus")
    assert result.response.status == "out_of_scope"
    assert result.response.citations == []
    llm.generate_grounded_answer.assert_not_called()


@pytest.mark.asyncio
async def test_irrelevant_nonempty_retrieval_abstains_without_verified_evidence():
    service, _, _ = _service(
        [_chunk("This passage only discusses another medicine.")],
        GroundedAnswer(answer="", evidence=[], insufficient=True),
    )
    result = await service.process("What is Makin?")
    assert result.response.status == "out_of_scope"
    assert result.response.citations == []


@pytest.mark.asyncio
async def test_model_requested_escalation_returns_safe_message_without_citations():
    service, _, _ = _service(
        [_chunk()],
        GroundedAnswer(answer="", evidence=[], escalate=True),
    )
    result = await service.process("My father takes metformin and feels dizzy, what should I give him?")
    assert result.response.status == "escalated"
    assert result.response.citations == []
    assert "clinician" in result.response.answer.lower()


@pytest.mark.asyncio
async def test_emergency_is_escalated_before_retrieval_or_generation():
    service, retriever, llm = _service([], GroundedAnswer(answer="", evidence=[]))
    result = await service.process(
        "A patient accidentally swallowed a whole bottle of Panadol."
    )
    assert result.response.status == "escalated"
    assert result.response.citations == []
    retriever.retrieve.assert_not_called()
    llm.generate_grounded_answer.assert_not_called()


@pytest.mark.asyncio
async def test_chat_service_passes_reviewed_retrieval_threshold():
    service, retriever, _ = _service([], GroundedAnswer(answer="", evidence=[]))
    result = await service.process("Question")
    assert result.response.status == "out_of_scope"
    args, kwargs = retriever.retrieve.call_args
    assert kwargs.get("min_score") == 0.50 or args[-1] == 0.50
