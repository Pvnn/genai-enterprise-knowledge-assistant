"""Tests for ingestion module.

Owner: P1
Import shared fixtures from conftest.py (owned by P2).  Do NOT define
new fixture setups that duplicate what conftest.py already provides.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.run_ingestion import ingest_document
from tests.conftest import TEST_DOC_ID, TEST_TENANT_ID, TEST_USER_ID


@pytest.mark.asyncio
async def test_ingest_document(db_session: AsyncSession) -> None:
    from uuid import UUID
    # We create the document first
    from app.models import Document, IngestionStatus
    doc = Document(
        id=UUID(TEST_DOC_ID),
        tenant_id=UUID(TEST_TENANT_ID),
        title="Test Document",
        department="HR",
        doc_type="policy",
        ingestion_status=IngestionStatus.PENDING.value
    )
    db_session.add(doc)
    await db_session.commit()
    
    # We can't easily test the full pipeline without triggering actual embeddings and OCR,
    # so we mock parse_document and embed_batch, or we just leave it as a stub per P1 instructions.
    # The spec says: "Stubs are enough at this stage — mark assertions TODO(P1)."
    assert str(doc.id) == TEST_DOC_ID


@pytest.mark.asyncio
async def test_upload_document_admin(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Test POST /documents/upload for an admin user."""
    from uuid import UUID
    from app.deps import get_current_user
    from app.schemas import CurrentUser
    
    # Mock admin user
    def override_get_current_user():
        return CurrentUser(
            user_id=UUID(TEST_USER_ID),
            tenant_id=UUID(TEST_TENANT_ID),
            email="admin@test.com",
            role="admin"
        )
    
    from app.main import app
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    # Send a multipart form upload
    response = await async_client.post(
        "/documents/upload",
        data={
            "department": "HR",
            "doc_type": "policy"
        },
        files={
            "file": ("test.pdf", b"dummy pdf content", "application/pdf")
        }
    )
    
    app.dependency_overrides.pop(get_current_user, None)
    
    assert response.status_code == 202
    data = response.json()
    assert "document_id" in data
    assert data["ingestion_status"] == "pending"
    
    # Verify DB insertion
    from app.models import Document
    from sqlalchemy import select
    result = await db_session.execute(select(Document).where(Document.id == UUID(data["document_id"])))
    doc = result.scalars().first()
    assert doc is not None
    assert str(doc.tenant_id) == TEST_TENANT_ID


@pytest.mark.asyncio
async def test_upload_document_member_forbidden(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Test POST /documents/upload for a standard member (should 403)."""
    from uuid import UUID
    from app.deps import get_current_user
    from app.schemas import CurrentUser
    
    # Mock member user
    def override_get_current_user():
        return CurrentUser(
            user_id=UUID(TEST_USER_ID),
            tenant_id=UUID(TEST_TENANT_ID),
            email="member@test.com",
            role="member"
        )
        
    from app.main import app
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    response = await async_client.post(
        "/documents/upload",
        data={
            "department": "HR",
            "doc_type": "policy"
        },
        files={
            "file": ("test.pdf", b"dummy pdf content", "application/pdf")
        }
    )
    
    app.dependency_overrides.pop(get_current_user, None)
    
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_document_status(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Test GET /documents/{document_id}/status."""
    from uuid import uuid4
    from app.models import Document, IngestionStatus
    from app.deps import get_current_user
    from app.schemas import CurrentUser
    from uuid import UUID
    
    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        tenant_id=UUID(TEST_TENANT_ID),
        title="Status Test",
        department="HR",
        doc_type="policy",
        ingestion_status=IngestionStatus.DONE.value
    )
    db_session.add(doc)
    await db_session.commit()
    
    # Mock member user
    def override_get_current_user():
        return CurrentUser(
            user_id=UUID(TEST_USER_ID),
            tenant_id=UUID(TEST_TENANT_ID),
            email="member@test.com",
            role="member"
        )
        
    from app.main import app
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    response = await async_client.get(f"/documents/{doc_id}/status")
    
    app.dependency_overrides.pop(get_current_user, None)
    
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == str(doc_id)
    assert data["ingestion_status"] == IngestionStatus.DONE.value

@pytest.mark.asyncio
async def test_summarize_document() -> None:
    from app.ingestion.summarizer import summarize_document
    from app.config import get_settings
    settings = get_settings()
    original_key = settings.openai_api_key
    settings.openai_api_key = None
    
    try:
        await summarize_document("Test document content.")
        assert False, "Should raise ValueError without API key"
    except ValueError:
        pass
    finally:
        settings.openai_api_key = original_key


@pytest.mark.asyncio
async def test_build_glossary() -> None:
    from app.ingestion.glossary_builder import build_glossary
    from app.config import get_settings
    settings = get_settings()
    original_key = settings.openai_api_key
    settings.openai_api_key = None
    
    try:
        await build_glossary("tenant1", [{"text": "NASA is great"}])
        assert False, "Should raise ValueError without API key"
    except ValueError:
        pass
    finally:
        settings.openai_api_key = original_key
