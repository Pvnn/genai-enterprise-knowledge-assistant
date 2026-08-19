"""Tests for generation module.

Owner: P4
Import shared fixtures from conftest.py (owned by P2). Do NOT define
new fixture setups that duplicate what conftest.py already provides.

These are unit tests, not integration tests — generate_answer()'s own job is
control flow (call order, refuse-or-answer branching), not a DB query or a
ranking formula, so the real dependencies (retrieve_chunks, embed_text,
decide_refusal, the OpenAI call) are mocked. Each of those functions is
covered by its OWNING tag's own test file (test_retrieval.py, test_embeddings.py,
test_grounding.py).

Known gap : as of this test file, P5's
grounding.decide_refusal() is still a stub that raises NotImplementedError,
so these tests patch app.generation.generator.decide_refusal directly rather
than relying on the real one. Once P5 lands the real implementation, add an
end-to-end test alongside these that doesn't mock decide_refusal.
"""

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.generation.generator import _dedupe_by_chunk_id, generate_answer
from app.schemas import ChatRequest, ChunkResult, RefusalDecision
from tests.conftest import TEST_TENANT_ID

TENANT_UUID = UUID(TEST_TENANT_ID)


def _stable_uuid(s: str) -> UUID:
    """Deterministic UUID so the same label string always maps to the same id."""
    return UUID(int=abs(hash(s)) % (2**128))


def _chunk(chunk_id: str, score: float) -> ChunkResult:
    return ChunkResult(
        chunk_id=_stable_uuid(chunk_id),
        document_id=UUID(int=1),
        text="fake chunk text",
        section_path="3.2.2",
        score=score,
    )


def _fake_openai_response(content: str):
    from unittest.mock import MagicMock

    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


async def _collect(request, db_session):
    return [event async for event in generate_answer(request, db_session)]


@pytest.mark.asyncio
async def test_zero_chunks_refuses_without_calling_the_llm_to_draft(db_session):
    """Step 6's zero-chunk optimization — decide_refusal's zero-chunk rule refuses
    regardless of draft content, so drafting from nothing would waste an API call.
    """
    request = ChatRequest(query="what is the leave policy", tenant_id=TENANT_UUID)

    with (
        patch("app.generation.generator._rewrite_query", None),
        patch("app.generation.generator._route_query", None),
        patch("app.generation.generator._hybrid_retrieve_chunks", None),
        patch("app.generation.generator._rerank", None),
        patch("app.generation.generator.embed_text", AsyncMock(return_value=[0.0] * 768)),
        patch("app.generation.generator.retrieve_chunks", AsyncMock(return_value=[])),
        patch(
            "app.generation.generator._draft_answer",
            AsyncMock(side_effect=AssertionError("must not be called with zero chunks")),
        ),
        patch(
            "app.generation.generator.decide_refusal",
            AsyncMock(
                return_value=RefusalDecision(
                    refused=True, reason="no_matching_documents", confidence=0.0, conflict=False
                )
            ),
        ),
    ):
        events = await _collect(request, db_session)

    assert [e["type"] for e in events] == ["final"]
    final = events[0]
    assert final["refused"] is True
    assert final["refusal_reason"] == "no_matching_documents"
    assert final["answer"] == ""  # required str field, must not be None
    assert final["citations"] == []


@pytest.mark.asyncio
async def test_high_score_chunk_streams_tokens_then_a_final_answer_with_citations(db_session):
    top_chunk = _chunk("c1", 0.9)
    request = ChatRequest(query="can I carry forward leave", tenant_id=TENANT_UUID)

    with (
        patch("app.generation.generator._rewrite_query", None),
        patch("app.generation.generator._route_query", None),
        patch("app.generation.generator._hybrid_retrieve_chunks", None),
        patch("app.generation.generator._rerank", None),
        patch("app.generation.generator.embed_text", AsyncMock(return_value=[0.0] * 768)),
        patch("app.generation.generator.retrieve_chunks", AsyncMock(return_value=[top_chunk])),
        patch(
            "app.generation.generator._client.chat.completions.create",
            AsyncMock(return_value=_fake_openai_response("Employees may carry forward unused leave.")),
        ),
        patch(
            "app.generation.generator.decide_refusal",
            AsyncMock(return_value=RefusalDecision(refused=False, reason=None, confidence=0.9, conflict=False)),
        ),
    ):
        events = await _collect(request, db_session)

    assert events[-1]["type"] == "final"
    final = events[-1]
    assert final["refused"] is False
    assert final["answer"] == "Employees may carry forward unused leave."
    assert len(final["citations"]) == 1
    assert final["citations"][0]["chunk_id"] == str(top_chunk.chunk_id)
    assert any(e["type"] == "token" for e in events[:-1])


@pytest.mark.asyncio
async def test_low_score_chunk_below_threshold_refuses(db_session):
    """A chunk exists, but decide_refusal (P5's job) says it isn't confident enough —
    this test only confirms generate_answer() obeys that decision correctly.
    """
    low_chunk = _chunk("c1", 0.5)
    request = ChatRequest(query="an obscure question", tenant_id=TENANT_UUID)

    with (
        patch("app.generation.generator._rewrite_query", None),
        patch("app.generation.generator._route_query", None),
        patch("app.generation.generator._hybrid_retrieve_chunks", None),
        patch("app.generation.generator._rerank", None),
        patch("app.generation.generator.embed_text", AsyncMock(return_value=[0.0] * 768)),
        patch("app.generation.generator.retrieve_chunks", AsyncMock(return_value=[low_chunk])),
        patch(
            "app.generation.generator._client.chat.completions.create",
            AsyncMock(return_value=_fake_openai_response("some draft")),
        ),
        patch(
            "app.generation.generator.decide_refusal",
            AsyncMock(
                return_value=RefusalDecision(
                    refused=True, reason="not_confident_retrieval", confidence=0.5, conflict=False
                )
            ),
        ),
    ):
        events = await _collect(request, db_session)

    assert [e["type"] for e in events] == ["final"]
    assert events[0]["refused"] is True
    assert events[0]["refusal_reason"] == "not_confident_retrieval"


@pytest.mark.asyncio
async def test_needs_clarification_yields_clarify_and_stops(db_session):
    from app.schemas import MetadataFilters, RewriteResult

    clarify_result = RewriteResult(
        expanded_query="",
        metadata_filters=MetadataFilters(),
        bm25_variant="",
        dense_variant="",
        sub_queries=[],
        needs_clarification=True,
        clarifying_question="Which department's policy do you mean?",
    )
    request = ChatRequest(query="what's the policy", tenant_id=TENANT_UUID)

    with patch("app.generation.generator._rewrite_query", AsyncMock(return_value=clarify_result)):
        events = await _collect(request, db_session)

    assert [e["type"] for e in events] == ["clarify"]
    assert events[0]["question"] == "Which department's policy do you mean?"


@pytest.mark.asyncio
async def test_unexpected_error_surfaces_as_a_safe_refusal_event_not_a_dead_stream(db_session):
    """Addition beyond the literal spec (flagged in generator.py): an unhandled
    error anywhere in the pipeline must not just kill the SSE stream silently.
    """
    request = ChatRequest(query="anything", tenant_id=TENANT_UUID)

    with (
        patch("app.generation.generator._rewrite_query", None),
        patch(
            "app.generation.generator.embed_text",
            AsyncMock(side_effect=RuntimeError("simulated embedding failure")),
        ),
    ):
        events = await _collect(request, db_session)

    assert [e["type"] for e in events] == ["final"]
    assert events[0]["refused"] is True
    assert events[0]["refusal_reason"] == "internal_error"


def test_dedupe_by_chunk_id_keeps_the_higher_score_for_duplicate_chunks():
    """Pure function used by Step 5 (merging sub-query results)."""
    dup_id = UUID(int=42)
    low = ChunkResult(chunk_id=dup_id, document_id=UUID(int=1), text="x", section_path="1", score=0.4)
    high = ChunkResult(chunk_id=dup_id, document_id=UUID(int=1), text="x", section_path="1", score=0.8)
    other = ChunkResult(chunk_id=UUID(int=43), document_id=UUID(int=1), text="y", section_path="2", score=0.6)

    merged = _dedupe_by_chunk_id([low, high, other])

    assert len(merged) == 2
    assert merged[0].chunk_id == dup_id
    assert merged[0].score == 0.8  # kept the higher of the two duplicate scores
    assert merged[1].chunk_id == other.chunk_id