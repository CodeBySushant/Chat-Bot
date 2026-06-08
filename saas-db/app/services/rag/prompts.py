"""Prompt construction: grounding (anti-hallucination) system prompt, message
assembly with conversation memory, and follow-up query expansion.
"""
from __future__ import annotations

from app.services.ai import ChatMessage

# Follow-up cues: short questions or ones leaning on prior turns.
_FOLLOWUP_CUES = (
    "it", "its", "they", "them", "that", "this", "those", "these", "he", "she",
    "and", "what about", "how about", "why", "tell me more", "more", "also",
)

SYSTEM_TEMPLATE = """{persona}

Answer the user's question using ONLY the information in the Context section below.

Rules:
- If the answer is not contained in the context, say you don't have enough information; do not invent facts.
- Be concise and accurate. Do not use outside knowledge.
- Cite the sources you used with bracketed numbers like [1], [2] that match the context.
- If the user asks a follow-up, use the conversation so far for pronouns/references, but still ground answers in the context."""

FALLBACK_ANSWER = (
    "I don't have enough information in the knowledge base to answer that. "
    "Could you rephrase, or ask about something covered by the available documents?"
)


def build_retrieval_query(question: str, history: list[ChatMessage]) -> str:
    """Expand a terse follow-up with the previous user turn for better recall."""
    q = question.strip()
    lowered = q.lower()
    is_followup = len(q.split()) <= 6 or lowered.startswith(_FOLLOWUP_CUES)
    if not is_followup:
        return q
    prev_user = next(
        (m.content for m in reversed(history) if m.role == "user"), None
    )
    return f"{prev_user} {q}" if prev_user else q


def build_messages(
    *,
    persona: str,
    context_text: str,
    history: list[ChatMessage],
    question: str,
) -> list[ChatMessage]:
    messages: list[ChatMessage] = [
        ChatMessage("system", SYSTEM_TEMPLATE.format(persona=persona))
    ]
    # Conversation memory (already trimmed to the recent window by the caller).
    messages.extend(history)
    context_block = context_text if context_text else "(no relevant context found)"
    messages.append(
        ChatMessage(
            "user",
            f"Context:\n{context_block}\n\nQuestion: {question}",
        )
    )
    return messages
