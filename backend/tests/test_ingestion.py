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
    """Stub test for ingest_document() with the new 4-arg signature."""
    # TODO (P1): Implement test logic
    # await ingest_document(file_path="...", tenant_id=TEST_TENANT_ID, department="HR", doc_type="policy")
    pass


@pytest.mark.asyncio
async def test_upload_document_admin(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Stub test for POST /documents/upload for an admin user."""
    # TODO (P1): Implement test logic for successful upload dispatch
    # current_user.role == "admin" is required.
    pass


@pytest.mark.asyncio
async def test_upload_document_member_forbidden(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Stub test for POST /documents/upload for a standard member (should 403)."""
    # TODO (P1): Implement test logic expecting HTTP 403
    pass


@pytest.mark.asyncio
async def test_get_document_status(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Stub test for GET /documents/{document_id}/status."""
    # TODO (P1): Implement test logic
    pass
