"""Conversations router – exposes CRUD endpoints for sidebar chat history threads.

Owner: P2
Endpoints:
  GET    /conversations                      - List all conversations for the authenticated user
  POST   /conversations                      - Create a new conversation
  GET    /conversations/{conversation_id}    - Get full conversation details and messages
  PATCH  /conversations/{conversation_id}    - Rename a conversation title
  DELETE /conversations/{conversation_id}    - Delete a conversation and its messages
  POST   /conversations/{conversation_id}/messages - Append a message to a conversation thread
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUserDep, DbDep
from app.models import Conversation, Message
from app.schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    ConversationUpdate,
    MessageCreate,
    MessageResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    db: DbDep,
    current_user: CurrentUserDep,
) -> list[ConversationSummary]:
    """List all conversation threads belonging to the authenticated user."""
    stmt = (
        select(Conversation)
        .where(
            Conversation.tenant_id == current_user.tenant_id,
            Conversation.user_id == current_user.user_id,
        )
        .options(selectinload(Conversation.messages))
        .order_by(Conversation.updated_at.desc())
    )
    result = await db.execute(stmt)
    conversations = result.scalars().all()

    return [
        ConversationSummary(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            message_count=len(c.messages),
        )
        for c in conversations
    ]


@router.post("", response_model=ConversationSummary, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    db: DbDep,
    current_user: CurrentUserDep,
) -> ConversationSummary:
    """Create a new conversation thread."""
    conv = Conversation(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        title=payload.title.strip() if payload.title and payload.title.strip() else "New Conversation",
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    return ConversationSummary(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0,
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> ConversationDetail:
    """Fetch a single conversation with its full message history."""
    stmt = (
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == current_user.tenant_id,
            Conversation.user_id == current_user.user_id,
        )
        .options(selectinload(Conversation.messages))
    )
    result = await db.execute(stmt)
    conv = result.scalars().first()

    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )

    # Sort messages chronologically
    sorted_messages = sorted(conv.messages, key=lambda m: m.created_at)

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            MessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                citations=m.citations,
                confidence=m.confidence,
                refused=m.refused,
                refusal_reason=m.refusal_reason,
                created_at=m.created_at,
            )
            for m in sorted_messages
        ],
    )


@router.patch("/{conversation_id}", response_model=ConversationSummary)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    db: DbDep,
    current_user: CurrentUserDep,
) -> ConversationSummary:
    """Rename a conversation title."""
    stmt = (
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == current_user.tenant_id,
            Conversation.user_id == current_user.user_id,
        )
        .options(selectinload(Conversation.messages))
    )
    result = await db.execute(stmt)
    conv = result.scalars().first()

    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )

    conv.title = payload.title.strip() if payload.title.strip() else "New Conversation"
    conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    await db.refresh(conv)

    return ConversationSummary(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=len(conv.messages),
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> dict:
    """Delete a conversation thread and all its messages."""
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.tenant_id == current_user.tenant_id,
        Conversation.user_id == current_user.user_id,
    )
    result = await db.execute(stmt)
    conv = result.scalars().first()

    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )

    await db.delete(conv)
    await db.commit()

    return {"status": "deleted", "id": str(conversation_id)}


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def append_message(
    conversation_id: UUID,
    payload: MessageCreate,
    db: DbDep,
    current_user: CurrentUserDep,
) -> MessageResponse:
    """Append a user or assistant message to a conversation thread."""
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.tenant_id == current_user.tenant_id,
        Conversation.user_id == current_user.user_id,
    )
    result = await db.execute(stmt)
    conv = result.scalars().first()

    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )

    msg = Message(
        conversation_id=conversation_id,
        tenant_id=current_user.tenant_id,
        role=payload.role,
        content=payload.content,
        citations=payload.citations if isinstance(payload.citations, (dict, list)) else None,
        confidence=payload.confidence,
        refused=payload.refused,
        refusal_reason=payload.refusal_reason,
    )
    db.add(msg)
    conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    await db.refresh(msg)

    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        citations=msg.citations,
        confidence=msg.confidence,
        refused=msg.refused,
        refusal_reason=msg.refusal_reason,
        created_at=msg.created_at,
    )
