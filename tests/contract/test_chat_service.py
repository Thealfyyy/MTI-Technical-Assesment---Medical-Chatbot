from unittest.mock import AsyncMock, MagicMock

import pytest

from app.generation.llm_client import ExtractiveAnswer
from app.schemas.chunk import RetrievedChunk
from app.services.chat_service import ChatService


def _chunk(text="Cataflam contains Diclofenac potassium."):
    return RetrievedChunk(
        doc_id="KB-03", title="Pain & Fever", section="NSAIDs > Trade Names", chunk_id="KB-03-C001",
        snippet=text, text=text, score=0.8, rank=1, source="hybrid",
    )


@pytest.mark.asyncio
async def test_safe_response_uses_only_verified_source_quote_and_citation():
    retriever = MagicMock()
    retriever.retrieve.return_value = [_chunk()]
    llm = MagicMock()
    llm.extract_supported_quotes = AsyncMock(return_value=ExtractiveAnswer(
        quotes=[("KB-03-C001", "Cataflam contains Diclofenac potassium.")], prompt_tokens=90, completion_tokens=20
    ))
    result = await ChatService(retriever=retriever, llm=llm).process("What is Cataflam?")
    assert result.response.status == "answered"
    assert result.response.answer == "Cataflam contains Diclofenac potassium."
    assert result.response.citations[0].doc_id == "KB-03"
    assert result.prompt_tokens == 90


@pytest.mark.asyncio
async def test_empty_retrieval_abstains_without_calling_llm():
    retriever = MagicMock()
    retriever.retrieve.return_value = []
    llm = MagicMock()
    llm.extract_supported_quotes = AsyncMock()
    result = await ChatService(retriever=retriever, llm=llm).process("Question outside the corpus")
    assert result.response.status == "out_of_scope"
    assert result.response.citations == []
    llm.extract_supported_quotes.assert_not_called()


@pytest.mark.asyncio
async def test_irrelevant_nonempty_retrieval_abstains_when_no_exact_source_quote():
    retriever = MagicMock()
    retriever.retrieve.return_value = [_chunk("This passage only discusses another medicine.")]
    llm = MagicMock()
    llm.extract_supported_quotes = AsyncMock(return_value=ExtractiveAnswer(quotes=[]))
    result = await ChatService(retriever=retriever, llm=llm).process("What is Makin?")
    assert result.response.status == "out_of_scope"
    assert result.response.citations == []


@pytest.mark.asyncio
async def test_emergency_is_escalated_before_retrieval_or_generation():
    retriever = MagicMock()
    llm = MagicMock()
    result = await ChatService(retriever=retriever, llm=llm).process(
        "A patient accidentally swallowed a whole bottle of Panadol."
    )
    assert result.response.status == "escalated"
    assert result.response.citations == []
    retriever.retrieve.assert_not_called()
    llm.extract_supported_quotes.assert_not_called()


@pytest.mark.asyncio
async def test_chat_service_passes_reviewed_retrieval_threshold():
    retriever = MagicMock()
    retriever.retrieve.return_value = []
    llm = MagicMock()
    result = await ChatService(retriever=retriever, llm=llm).process("Question")
    assert result.response.status == "out_of_scope"
    args, kwargs = retriever.retrieve.call_args
    assert kwargs.get("min_score") == 0.50 or args[-1] == 0.50
