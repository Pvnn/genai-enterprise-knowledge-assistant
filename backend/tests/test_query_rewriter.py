"""Tests for app/generation/query_rewriter.py — Stage 1 query rewriting (Priority 2).

Owner: P4
Import shared fixtures from conftest.py (owned by P2). Do NOT define new
fixture setups that duplicate what conftest.py already provides.

These don't hit the real OpenAI API or a real seeded database — the glossary
lookup is tested against the real in-memory test database (via db_session,
inserting a couple of Glossary rows), and the OpenAI call is mocked, since
controlling its output is exactly what these tests need to do.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.generation.query_rewriter import _load_glossary, rewrite
from app.models import Glossary
from tests.conftest import TEST_TENANT_ID

TENANT_UUID = UUID(TEST_TENANT_ID)


async def _seed_enterprise(session: AsyncSession) -> None:
    """Glossary.tenant_id is a foreign key into enterprises — seed one row first,
    matching the pattern already used in test_retrieval.py.
    """
    await session.execute(
        text("INSERT INTO enterprises (id, name, created_at) VALUES (:id, 'Test Corp', datetime('now'))"),
        {"id": str(TENANT_UUID)},
    )


def _fake_openai_response(payload: dict):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=json.dumps(payload)))]
    return response


@pytest.mark.asyncio
async def test_load_glossary_returns_entries_for_the_given_tenant(db_session):
    await _seed_enterprise(db_session)
    db_session.add_all(
        [
            Glossary(tenant_id=TENANT_UUID, term="PTO", expansion="Paid Time Off"),
            Glossary(tenant_id=TENANT_UUID, term="GR", expansion="Government Resolution"),
        ]
    )
    await db_session.flush()

    glossary = await _load_glossary(db_session, TENANT_UUID)

    assert glossary == {"PTO": "Paid Time Off", "GR": "Government Resolution"}


@pytest.mark.asyncio
async def test_load_glossary_returns_empty_dict_when_tenant_has_no_entries(db_session):
    await _seed_enterprise(db_session)

    glossary = await _load_glossary(db_session, TENANT_UUID)

    assert glossary == {}


@pytest.mark.asyncio
async def test_rewrite_returns_the_parsed_structured_shape_on_a_well_formed_llm_response(db_session):
    payload = {
        "expanded_query": "what is the Paid Time Off carry-forward policy",
        "metadata_filters": {"department": None, "doc_type": "leave_policy", "version_status": None},
        "bm25_variant": "PTO carry forward policy",
        "dense_variant": "can employees carry forward unused paid time off",
        "sub_queries": [],
        "needs_clarification": False,
        "clarifying_question": None,
    }

    with patch(
        "app.generation.query_rewriter._client.chat.completions.create",
        AsyncMock(return_value=_fake_openai_response(payload)),
    ):
        result = await rewrite("can I carry forward PTO", TENANT_UUID, db_session)

    assert result.expanded_query == payload["expanded_query"]
    assert result.metadata_filters.doc_type == "leave_policy"
    assert result.bm25_variant == payload["bm25_variant"]
    assert result.needs_clarification is False


@pytest.mark.asyncio
async def test_rewrite_ignores_an_unsupported_role_field_instead_of_erroring(db_session):
    """MetadataFilters has no `role` field (flagged in the module docstring) — a
    response that includes one should be handled gracefully, not crash.
    """
    payload = {
        "expanded_query": "what is the student leave policy",
        "metadata_filters": {"department": "academics", "doc_type": None, "role": "student", "version_status": None},
        "bm25_variant": "student leave policy",
        "dense_variant": "student leave policy",
        "sub_queries": [],
        "needs_clarification": False,
        "clarifying_question": None,
    }

    with patch(
        "app.generation.query_rewriter._client.chat.completions.create",
        AsyncMock(return_value=_fake_openai_response(payload)),
    ):
        result = await rewrite("what leave am I allowed as a student", TENANT_UUID, db_session)

    assert result.metadata_filters.department == "academics"
    assert not hasattr(result.metadata_filters, "role")


@pytest.mark.asyncio
async def test_rewrite_falls_back_to_raw_query_passthrough_when_llm_response_is_unparseable(db_session):
    # Missing the required "expanded_query" key -> KeyError inside rewrite(), caught internally.
    incomplete_payload = {"bm25_variant": "x", "dense_variant": "x"}

    with patch(
        "app.generation.query_rewriter._client.chat.completions.create",
        AsyncMock(return_value=_fake_openai_response(incomplete_payload)),
    ):
        result = await rewrite("raw user question", TENANT_UUID, db_session)

    assert result.expanded_query == "raw user question"
    assert result.bm25_variant == "raw user question"
    assert result.dense_variant == "raw user question"
    assert result.needs_clarification is False
    assert result.sub_queries == []