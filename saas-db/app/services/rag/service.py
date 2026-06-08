"""RAG orchestration.

Flow: question -> (follow-up expansion) -> embed -> Qdrant search -> hydrate +
rank -> build context window -> construct grounded prompt with memory -> AI
generation -> persist + return with sources.

The orchestrator opens its own tenant (RLS) sessions per step rather than reusing
a request session. This keeps streaming safe (the generator outlives the request
handler) and avoids the transaction-local GUC being cleared by intermediate
commits.
"""
from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.services import chatbot_service, conversation_service, usage_service, analytics_service
from app.services.ai import AIProviderError, get_chat_provider
from app.services.rag import prompts
from app.services.rag.context_builder import build_context
from app.services.rag.retrieval import RetrievedChunk, retrieve

logger = get_logger("app.rag")


@asynccontextmanager
async def _session(company_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    from app.db.session import SessionFactory

    async with SessionFactory() as db:
        await db.execute(
            text("SELECT set_config('app.current_company', :cid, true)"),
            {"cid": str(company_id)},
        )
        yield db


def _source(c: RetrievedChunk) -> dict:
    return {
        "document_id": c.document_id,
        "chunk_id": c.chunk_id,
        "chunk_index": c.chunk_index,
        "title": c.title,
        "source_uri": c.source_uri,
        "page_number": c.page_number,
        "score": round(c.score, 4),
        "snippet": (c.text or "")[:240],
    }


async def _meter_message(company_id, chatbot_id, conversation_id, text: str) -> None:
    """Record message + token usage and an analytics event (own GUC session)."""
    try:
        async with _session(company_id) as db:
            await usage_service.record_usage(db, company_id=company_id, metric="messages", chatbot_id=chatbot_id)
            await usage_service.record_usage(
                db, company_id=company_id, metric="ai_tokens",
                quantity=max(1, len(text) // 4), chatbot_id=chatbot_id)
            await analytics_service.record_event(
                db, company_id=company_id, chatbot_id=chatbot_id, conversation_id=conversation_id,
                event_type="message", event_name="assistant_reply")
            await db.commit()
    except Exception:  # metering must never break the chat response
        logger.warning("message metering failed", exc_info=True)


async def _prepare(company_id, chatbot_id, conversation_id, question, top_k):
    """Shared setup for both response modes: validate, load memory, retrieve."""
    async with _session(company_id) as db:
        chatbot = await chatbot_service.get_chatbot(db, chatbot_id=chatbot_id)
        conv = await conversation_service.get_conversation(
            db, conversation_id=conversation_id
        )
        if conv.chatbot_id != chatbot_id:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("Conversation not found")
        history = await conversation_service.load_history(
            db, conversation_id=conversation_id, turns=settings.RAG_HISTORY_TURNS
        )

    persona = chatbot.system_prompt or settings.RAG_PERSONA
    k = top_k or chatbot.top_k or settings.RAG_TOP_K
    temperature = float(chatbot.temperature)
    max_tokens = chatbot.max_tokens

    # Persist the user turn (conversation memory).
    async with _session(company_id) as db:
        await conversation_service.persist_message(
            db, company_id=company_id, conversation_id=conversation_id,
            role="user", content=question,
        )

    # Follow-up-aware retrieval query, then retrieve.
    rq = prompts.build_retrieval_query(question, history)
    async with _session(company_id) as db:
        chunks = await retrieve(
            db, company_id=company_id, chatbot_id=chatbot_id, query=rq,
            top_k=k, min_score=settings.RAG_MIN_SCORE,
        )
    return persona, history, temperature, max_tokens, chunks


async def answer(
    *,
    company_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    conversation_id: uuid.UUID,
    question: str,
    top_k: int | None = None,
) -> dict:
    persona, history, temperature, max_tokens, chunks = await _prepare(
        company_id, chatbot_id, conversation_id, question, top_k
    )

    if not chunks:
        answer_text, sources, model, latency, chunk_ids = (
            prompts.FALLBACK_ANSWER, [], None, None, []
        )
    else:
        ctx = build_context(chunks, max_chars=settings.RAG_MAX_CONTEXT_CHARS)
        messages = prompts.build_messages(
            persona=persona, context_text=ctx.text, history=history, question=question
        )
        provider = get_chat_provider()
        t0 = time.perf_counter()
        try:
            result = await provider.complete(
                messages, temperature=temperature, max_tokens=max_tokens
            )
        except AIProviderError as exc:
            logger.warning("AI generation failed: %s", exc)
            raise
        latency = int((time.perf_counter() - t0) * 1000)
        answer_text, model = result.text, result.model
        sources = [_source(c) for c in ctx.used]
        chunk_ids = [c.chunk_id for c in ctx.used]

    async with _session(company_id) as db:
        msg = await conversation_service.persist_message(
            db, company_id=company_id, conversation_id=conversation_id,
            role="assistant", content=answer_text, model=model,
            latency_ms=latency, retrieved_chunk_ids=chunk_ids, citations=sources,
        )

    await _meter_message(company_id, chatbot_id, conversation_id, answer_text)
    return {
        "conversation_id": str(conversation_id),
        "message_id": str(msg.id),
        "answer": answer_text,
        "sources": sources,
    }


async def answer_stream(
    *,
    company_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    conversation_id: uuid.UUID,
    question: str,
    top_k: int | None = None,
) -> AsyncIterator[dict]:
    persona, history, temperature, max_tokens, chunks = await _prepare(
        company_id, chatbot_id, conversation_id, question, top_k
    )

    if not chunks:
        yield {"type": "delta", "text": prompts.FALLBACK_ANSWER}
        async with _session(company_id) as db:
            msg = await conversation_service.persist_message(
                db, company_id=company_id, conversation_id=conversation_id,
                role="assistant", content=prompts.FALLBACK_ANSWER,
            )
        yield {"type": "done", "sources": [], "message_id": str(msg.id),
               "conversation_id": str(conversation_id)}
        return

    ctx = build_context(chunks, max_chars=settings.RAG_MAX_CONTEXT_CHARS)
    messages = prompts.build_messages(
        persona=persona, context_text=ctx.text, history=history, question=question
    )
    sources = [_source(c) for c in ctx.used]
    provider = get_chat_provider()
    parts: list[str] = []
    t0 = time.perf_counter()
    try:
        async for delta in provider.stream(
            messages, temperature=temperature, max_tokens=max_tokens
        ):
            parts.append(delta)
            yield {"type": "delta", "text": delta}
    except AIProviderError as exc:
        logger.warning("AI streaming failed: %s", exc)
        yield {"type": "error", "message": str(exc)}
        return

    full = "".join(parts)
    latency = int((time.perf_counter() - t0) * 1000)
    async with _session(company_id) as db:
        msg = await conversation_service.persist_message(
            db, company_id=company_id, conversation_id=conversation_id,
            role="assistant", content=full, model=None, latency_ms=latency,
            retrieved_chunk_ids=[c.chunk_id for c in ctx.used], citations=sources,
        )
    await _meter_message(company_id, chatbot_id, conversation_id, full)
    yield {"type": "done", "sources": sources, "message_id": str(msg.id),
           "conversation_id": str(conversation_id)}
