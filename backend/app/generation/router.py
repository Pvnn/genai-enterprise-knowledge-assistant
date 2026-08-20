"""Generation router – exposes POST /chat (SSE streaming).

Owner: P4
See Section 5 for the exact SSE event contract:
  - token events while generating
  - clarify event if needs_clarification (Priority 2)
  - final event with answer, citations, confidence, refused, conflict

Tenant isolation fix (flagged per Section 0 rule 6, Section 1 NFR): the
request body's tenant_id must never be trusted on its own — a client could
put any tenant_id in the request JSON. The authenticated user's own
tenant_id (from their verified login token, via current_user) is the only
trustworthy source, so it always overrides whatever the request body said.

Chat history persistence: the frontend (frontend/src/chat/ChatPage.tsx)
generates its own conversation_id client-side with crypto.randomUUID() and
sends it on every /chat request — it never calls POST /conversations first.
So this router does a get-or-create against that same id (see
_get_or_create_conversation) rather than requiring the conversation to
already exist. This means chat history now saves for real with no frontend
changes needed. Saving is fail-safe: any DB error while persisting history
is logged and swallowed, never allowed to break the actual chat response.
"""

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.deps import CurrentUserDep, DbDep
from app.generation.generator import generate_answer
from app.models import Conversation, Message
from app.schemas import ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_or_create_conversation(
    db: DbDep,
    current_user,
    conversation_id_str: str | None,
    first_query: str,
) -> Conversation:
    """Fetch the conversation this /chat request belongs to, creating it if
    this is the first message in that thread.

    The client (see ChatPage.tsx) already generates a conversation_id on its
    own before ever calling the backend, so we honor that id rather than
    minting a new one — this keeps the existing frontend flow working
    unchanged while making the conversation durable server-side.
    """
    conv_id: UUID | None = None
    if conversation_id_str:
        try:
            conv_id = UUID(conversation_id_str)
        except ValueError:
            logger.warning("Ignoring malformed conversation_id=%r", conversation_id_str)
            conv_id = None

    if conv_id is not None:
        stmt = select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.tenant_id == current_user.tenant_id,
            Conversation.user_id == current_user.user_id,
        )
        result = await db.execute(stmt)
        existing = result.scalars().first()
        if existing is not None:
            return existing

    conv_kwargs = {
        "tenant_id": current_user.tenant_id,
        "user_id": current_user.user_id,
        "title": (first_query or "").strip()[:60] or "New Conversation",
    }
    if conv_id is not None:
        # Preserve the client-generated id instead of letting the model
        # mint a fresh one, so the frontend's own id keeps working as the
        # key for this thread on every future message.
        conv_kwargs["id"] = conv_id

    conv = Conversation(**conv_kwargs)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def _save_message(
    db: DbDep,
    conversation: Conversation,
    tenant_id: UUID,
    *,
    role: str,
    content: str,
    citations: list | dict | None = None,
    confidence: float | None = None,
    refused: bool = False,
    refusal_reason: str | None = None,
) -> None:
    """Persist one chat-history message.

    Fail-safe by design: a history-saving error must never take down the
    actual /chat response, so any exception here is logged and swallowed
    (matching the fail-safe pattern already used by the reranker and
    grounding refusal logic elsewhere in this pipeline).
    """
    try:
        msg = Message(
            conversation_id=conversation.id,
            tenant_id=tenant_id,
            role=role,
            content=content,
            citations=citations,
            confidence=confidence,
            refused=refused,
            refusal_reason=refusal_reason,
        )
        db.add(msg)
        conversation.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
    except Exception as exc:
        logger.warning("Failed to save chat history message (role=%s): %s", role, exc)
        try:
            await db.rollback()
        except Exception as rb_exc:
            logger.debug("Rollback after failed history save also failed: %s", rb_exc)


@router.post("/chat")
async def chat(
    request: ChatRequest,
    db: DbDep,
    current_user: CurrentUserDep,
) -> StreamingResponse:
    """Stream a grounded answer to a user query over Server-Sent Events."""

    if request.tenant_id != current_user.tenant_id:
        logger.warning(
            "tenant_id mismatch on /chat: request declared %s but authenticated user "
            "belongs to %s — overriding with the authenticated tenant_id",
            request.tenant_id,
            current_user.tenant_id,
        )
    request.tenant_id = current_user.tenant_id  # never trust the client-supplied value

    conversation = await _get_or_create_conversation(
        db, current_user, request.conversation_id, request.query
    )
    await _save_message(
        db,
        conversation,
        current_user.tenant_id,
        role="user",
        content=request.query,
    )

    async def event_stream():
        final_payload: dict | None = None
        async for event in generate_answer(request, db):
            if event.get("type") == "final":
                final_payload = event
            yield f"data: {json.dumps(event)}\n\n"

        if final_payload is not None:
            await _save_message(
                db,
                conversation,
                current_user.tenant_id,
                role="assistant",
                content=final_payload.get("answer", ""),
                citations=final_payload.get("citations"),
                confidence=final_payload.get("confidence"),
                refused=final_payload.get("refused", False),
                refusal_reason=final_payload.get("refusal_reason"),
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
