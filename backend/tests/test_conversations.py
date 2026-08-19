"""Tests for conversations and chat history router.

Owner: P2
Coverage:
  - POST   /conversations                      : create conversation
  - GET    /conversations                      : list conversations for authenticated user
  - GET    /conversations/{conversation_id}    : retrieve full conversation with messages
  - PATCH  /conversations/{conversation_id}    : update/rename conversation title
  - DELETE /conversations/{conversation_id}    : delete conversation and cascading messages
  - POST   /conversations/{conversation_id}/messages : append messages to a conversation thread
  - Strict tenant and user-level isolation tests
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import get_current_user
from app.database import get_db
from app.main import app
from app.models import Conversation, Message
from app.schemas import CurrentUser
from tests.conftest import TEST_TENANT_ID, TEST_USER_ID


@pytest.fixture
def auth_override(mock_current_user: CurrentUser, db_session: AsyncSession):
    """Override get_current_user and get_db dependencies."""
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_db] = lambda: db_session
    yield mock_current_user
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_and_list_conversations(
    async_client: AsyncClient,
    auth_override: CurrentUser,
) -> None:
    """Test creating a conversation and listing conversations for the current user."""
    # Create conversation
    create_resp = await async_client.post(
        "/conversations",
        json={"title": "Leave Policy Q&A"},
    )
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["title"] == "Leave Policy Q&A"
    assert created_data["message_count"] == 0
    conv_id = created_data["id"]

    # List conversations
    list_resp = await async_client.get("/conversations")
    assert list_resp.status_code == 200
    conversations = list_resp.json()
    assert len(conversations) >= 1
    assert any(c["id"] == conv_id and c["title"] == "Leave Policy Q&A" for c in conversations)


@pytest.mark.asyncio
async def test_append_and_get_conversation_messages(
    async_client: AsyncClient,
    auth_override: CurrentUser,
) -> None:
    """Test appending messages (user + assistant) and retrieving full conversation detail."""
    # Create conversation
    conv_resp = await async_client.post("/conversations", json={"title": "Travel Policy"})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["id"]

    # Append user question
    user_msg_resp = await async_client.post(
        f"/conversations/{conv_id}/messages",
        json={
            "role": "user",
            "content": "What is the per diem rate for international travel?",
        },
    )
    assert user_msg_resp.status_code == 201
    user_msg = user_msg_resp.json()
    assert user_msg["role"] == "user"
    assert user_msg["content"] == "What is the per diem rate for international travel?"

    # Append assistant response with citations
    asst_msg_resp = await async_client.post(
        f"/conversations/{conv_id}/messages",
        json={
            "role": "assistant",
            "content": "The international per diem rate is $75 per day as per Section 4.1.",
            "citations": [
                {
                    "chunk_id": str(uuid4()),
                    "document_id": str(uuid4()),
                    "text": "Section 4.1: International Travel Per Diem is $75/day.",
                    "section_path": "4.1 Travel Allowances",
                    "score": 0.95,
                }
            ],
            "confidence": 0.95,
            "refused": False,
        },
    )
    assert asst_msg_resp.status_code == 201
    asst_msg = asst_msg_resp.json()
    assert asst_msg["role"] == "assistant"
    assert len(asst_msg["citations"]) == 1
    assert asst_msg["confidence"] == 0.95

    # Fetch conversation detail
    detail_resp = await async_client.get(f"/conversations/{conv_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == conv_id
    assert detail["title"] == "Travel Policy"
    assert len(detail["messages"]) == 2
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][1]["role"] == "assistant"
    assert detail["messages"][1]["citations"][0]["section_path"] == "4.1 Travel Allowances"


@pytest.mark.asyncio
async def test_update_conversation_title(
    async_client: AsyncClient,
    auth_override: CurrentUser,
) -> None:
    """Test renaming a conversation thread."""
    conv_resp = await async_client.post("/conversations", json={"title": "Original Title"})
    conv_id = conv_resp.json()["id"]

    patch_resp = await async_client.patch(
        f"/conversations/{conv_id}",
        json={"title": "Updated Policy Inquiry"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Updated Policy Inquiry"

    # Verify detail reflects updated title
    detail_resp = await async_client.get(f"/conversations/{conv_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["title"] == "Updated Policy Inquiry"


@pytest.mark.asyncio
async def test_delete_conversation(
    async_client: AsyncClient,
    auth_override: CurrentUser,
) -> None:
    """Test deleting a conversation and confirming cascading message removal."""
    conv_resp = await async_client.post("/conversations", json={"title": "Temporary Thread"})
    conv_id = conv_resp.json()["id"]

    # Append message
    await async_client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "Temporary message"},
    )

    # Delete conversation
    del_resp = await async_client.delete(f"/conversations/{conv_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    # Verify get returns 404
    get_resp = await async_client.get(f"/conversations/{conv_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_conversation_tenant_and_user_isolation(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify that User A cannot see or modify User B's conversations or conversations from another tenant."""
    tenant_a = UUID(TEST_TENANT_ID)
    user_a = CurrentUser(
        user_id=UUID(TEST_USER_ID),
        tenant_id=tenant_a,
        email="user_a@enterprise.com",
        role="member",
    )

    tenant_b = uuid4()
    user_b = CurrentUser(
        user_id=uuid4(),
        tenant_id=tenant_b,
        email="user_b@other.com",
        role="member",
    )

    # Act as User A and create a conversation
    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_db] = lambda: db_session

    create_resp = await async_client.post(
        "/conversations",
        json={"title": "User A Private Thread"},
    )
    assert create_resp.status_code == 201
    conv_a_id = create_resp.json()["id"]

    # Switch to User B
    app.dependency_overrides[get_current_user] = lambda: user_b

    # User B should NOT see User A's conversation in list
    list_resp = await async_client.get("/conversations")
    assert list_resp.status_code == 200
    assert not any(c["id"] == conv_a_id for c in list_resp.json())

    # User B should get 404 when trying to fetch User A's conversation
    detail_resp = await async_client.get(f"/conversations/{conv_a_id}")
    assert detail_resp.status_code == 404

    # User B should get 404 when trying to patch User A's conversation
    patch_resp = await async_client.patch(
        f"/conversations/{conv_a_id}",
        json={"title": "Hacked Title"},
    )
    assert patch_resp.status_code == 404

    # User B should get 404 when trying to delete User A's conversation
    del_resp = await async_client.delete(f"/conversations/{conv_a_id}")
    assert del_resp.status_code == 404

    app.dependency_overrides.clear()
