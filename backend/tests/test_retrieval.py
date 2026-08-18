"""Tests for retrieval module.

Owner: P2
Tests dense retrieval, hybrid retrieval (RRF), coarse routing, and POST /retrieve endpoint.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from app.deps import get_current_user
from app.main import app
from app.retrieval.dense_retrieval import retrieve_chunks
from app.retrieval.hybrid_retrieval import hybrid_retrieve
from app.retrieval.routing import route_query
from app.schemas import CurrentUser, MetadataFilters, ScopedSection
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_DOC_ID, TEST_TENANT_ID

TENANT_UUID = UUID(TEST_TENANT_ID)
OTHER_TENANT_UUID = UUID("99999999-9999-9999-9999-999999999999")
DOC_UUID = UUID(TEST_DOC_ID)


async def _seed_test_data(session: AsyncSession) -> None:
    """Helper to seed enterprise, documents, and chunks."""
    # Seed enterprises
    await session.execute(
        text(
            "INSERT INTO enterprises (id, name, created_at) VALUES "
            "(:id1, 'Test Corp', datetime('now')), "
            "(:id2, 'Other Corp', datetime('now'))"
        ),
        {"id1": str(TENANT_UUID), "id2": str(OTHER_TENANT_UUID)},
    )

    # Seed documents
    section_tree_data = {
        "1. Overview": {},
        "2. Leave Policy": {
            "2.1 Casual Leave": {},
            "2.2 Earned Leave": {
                "2.2.1 Accrual": {},
                "2.2.2 Carry-forward": {},
            },
        },
    }

    await session.execute(
        text(
            "INSERT INTO documents (id, tenant_id, title, department, doc_type, version_status, source_path, summary, section_tree, ingestion_status) "
            "VALUES (:doc_id, :tenant_id, 'HR Leave Guidelines 2025', 'HR', 'policy', 'current', '/docs/hr_leave.pdf', "
            "'Comprehensive guidelines for employee leave and earned leave carry forward rules.', :section_tree, 'done')"
        ),
        {
            "doc_id": str(DOC_UUID),
            "tenant_id": str(TENANT_UUID),
            "section_tree": json.dumps(section_tree_data),
        },
    )

    # Seed chunks
    # Embedding 1 is very close to [1.0, 0.0, 0.0]
    # Embedding 2 is close to [0.0, 1.0, 0.0]
    # Embedding 3 belongs to other tenant
    chunk1_id = str(uuid4())
    chunk2_id = str(uuid4())
    chunk3_id = str(uuid4())

    emb1 = json.dumps([0.99, 0.05, 0.01] + [0.0] * 765)
    emb2 = json.dumps([0.05, 0.98, 0.02] + [0.0] * 765)
    emb3 = json.dumps([0.99, 0.05, 0.01] + [0.0] * 765)

    await session.execute(
        text(
            "INSERT INTO chunks (id, document_id, tenant_id, text, section_path, embedding, department, doc_type, version_status) "
            "VALUES "
            "(:c1, :d1, :t1, 'Employees may carry forward up to 15 days of earned leave each calendar year.', '2.2.2 Carry-forward', :emb1, 'HR', 'policy', 'current'), "
            "(:c2, :d1, :t1, 'Engineering coding guidelines and repository permissions.', '1. Overview', :emb2, 'Engineering', 'guideline', 'current'), "
            "(:c3, :d1, :t2, 'Other tenant confidential document.', '1. Overview', :emb3, 'HR', 'policy', 'current')"
        ),
        {
            "c1": chunk1_id,
            "c2": chunk2_id,
            "c3": chunk3_id,
            "d1": str(DOC_UUID),
            "t1": str(TENANT_UUID),
            "t2": str(OTHER_TENANT_UUID),
            "emb1": emb1,
            "emb2": emb2,
            "emb3": emb3,
        },
    )
    await session.flush()


@pytest.mark.asyncio
async def test_dense_retrieval_ranking_and_isolation(db_session: AsyncSession) -> None:
    """Verify pgvector dense search returns top matching chunks and isolates tenants."""
    await _seed_test_data(db_session)

    query_vec = [1.0, 0.0, 0.0] + [0.0] * 765
    filters = MetadataFilters()

    results = await retrieve_chunks(
        query_embedding=query_vec,
        tenant_id=TENANT_UUID,
        filters=filters,
        top_k=10,
        session=db_session,
    )

    assert len(results) == 2
    # First chunk should have highest similarity score
    assert "carry forward" in results[0].text
    assert results[0].section_path == "2.2.2 Carry-forward"
    assert results[0].score > results[1].score
    assert results[0].source_path == "/docs/hr_leave.pdf"

    # Verify other tenant data is not retrieved
    all_texts = [r.text for r in results]
    assert "Other tenant confidential document." not in all_texts


@pytest.mark.asyncio
async def test_dense_retrieval_metadata_filters(db_session: AsyncSession) -> None:
    """Verify department, doc_type, and version_status filters work properly."""
    await _seed_test_data(db_session)

    query_vec = [1.0, 0.0, 0.0] + [0.0] * 765

    # Filter by Engineering
    results = await retrieve_chunks(
        query_embedding=query_vec,
        tenant_id=TENANT_UUID,
        filters=MetadataFilters(department="Engineering"),
        top_k=10,
        session=db_session,
    )

    assert len(results) == 1
    assert results[0].department == "Engineering"
    assert "Engineering coding guidelines" in results[0].text


@pytest.mark.asyncio
async def test_dense_retrieval_scoped_sections(db_session: AsyncSession) -> None:
    """Verify search is restricted when scoped_sections are provided."""
    await _seed_test_data(db_session)

    query_vec = [0.0, 1.0, 0.0] + [0.0] * 765

    scoped = [
        ScopedSection(
            document_id=DOC_UUID,
            section_path="2.2.2 Carry-forward",
        )
    ]

    results = await retrieve_chunks(
        query_embedding=query_vec,
        tenant_id=TENANT_UUID,
        filters=MetadataFilters(),
        top_k=10,
        session=db_session,
        scoped_sections=scoped,
    )

    assert len(results) == 1
    assert results[0].section_path == "2.2.2 Carry-forward"


@pytest.mark.asyncio
async def test_hybrid_retrieval_rrf(db_session: AsyncSession) -> None:
    """Verify hybrid search fuses dense and keyword matches with RRF."""
    await _seed_test_data(db_session)

    query_vec = [1.0, 0.0, 0.0] + [0.0] * 765
    bm25_query = "carry forward earned leave"

    results = await hybrid_retrieve(
        bm25_query=bm25_query,
        query_embedding=query_vec,
        tenant_id=TENANT_UUID,
        filters=MetadataFilters(),
        top_k=5,
        session=db_session,
    )

    assert len(results) > 0
    # Top result should be the leave policy carry-forward chunk
    assert "carry forward" in results[0].text
    assert results[0].score > 0.0


@pytest.mark.asyncio
async def test_route_query(db_session: AsyncSession) -> None:
    """Verify Stage 2 coarse routing selects governing sections."""
    await _seed_test_data(db_session)

    routes = await route_query(
        rewritten_query="can I carry forward leave",
        tenant_id=TENANT_UUID,
        session=db_session,
    )

    assert len(routes) > 0
    assert routes[0]["document_id"] == DOC_UUID
    assert "Leave" in routes[0]["section_path"] or "Carry-forward" in routes[0]["section_path"]


@pytest.mark.asyncio
async def test_retrieve_api_endpoint(async_client: AsyncClient, db_session: AsyncSession, mock_current_user: CurrentUser) -> None:
    """Verify POST /retrieve endpoint returns formatted ChunkResults and enforces tenant isolation."""
    await _seed_test_data(db_session)

    app.dependency_overrides[get_current_user] = lambda: mock_current_user

    mock_vec = [1.0, 0.0, 0.0] + [0.0] * 765
    with patch("app.retrieval.router.embed_text", new_callable=AsyncMock, return_value=mock_vec):
        response = await async_client.post(
            "/retrieve",
            json={
                "query": "How many days of leave can I carry forward?",
                "tenant_id": str(OTHER_TENANT_UUID),  # Should be overridden by auth tenant_id
                "top_k": 5,
                "filters": {
                    "department": "HR",
                },
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "chunks" in data
    assert len(data["chunks"]) == 1
    assert "carry forward" in data["chunks"][0]["text"]
    assert data["chunks"][0]["department"] == "HR"
