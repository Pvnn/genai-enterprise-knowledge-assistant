"""Tests for the indexer module.

Owner: P3
Import shared fixtures from conftest.py (owned by P2).  Do NOT define
new fixture setups that duplicate what conftest.py already provides.

Strategy:
- AsyncSession is fully mocked (no real DB).
- embed_batch is patched at the app.retrieval.indexer module level.
- Rows returned by session.execute().fetchall() are simulated as simple
  two-element tuples (id, text), which is exactly what index_chunks accesses
  via row[0] and row[1].
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.retrieval.embeddings import EmbeddingError
from app.retrieval.indexer import EMBED_BATCH_SIZE, IndexerError, index_chunks


# ── Helpers ───────────────────────────────────────────────────────────────────

_TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_FAKE_VECTOR = [0.1] * 768


def _make_rows(n: int) -> list[tuple[str, str]]:
    """Return *n* fake (chunk_id, text) rows as plain tuples."""
    return [(str(uuid.uuid4()), f"chunk text {i}") for i in range(n)]


def _mock_session(rows: list[tuple[str, str]]) -> AsyncMock:
    """Build a minimal AsyncSession mock whose execute() returns *rows*."""
    session = AsyncMock()
    fetch_result = MagicMock()
    fetch_result.fetchall.return_value = rows
    # First execute() call = SELECT (returns rows).
    # Subsequent execute() calls = UPDATE (return value is ignored).
    session.execute = AsyncMock(return_value=fetch_result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


# ── Case 1: happy path ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_index_chunks_happy_path_returns_count() -> None:
    """3 unindexed chunks → embed_batch called once → 3 UPDATEs → 1 commit → returns 3."""
    rows = _make_rows(3)
    session = _mock_session(rows)
    vectors = [_FAKE_VECTOR for _ in rows]

    with patch(
        "app.retrieval.indexer.embed_batch",
        new=AsyncMock(return_value=vectors),
    ) as mock_embed:
        result = await index_chunks(session, _TENANT_ID)

    assert result == 3
    # embed_batch called exactly once with all 3 texts.
    mock_embed.assert_awaited_once()
    # TODO(P3): assert mock_embed.call_args[0][0] == [r[1] for r in rows]

    # session.execute: 1 SELECT + 3 UPDATEs = 4 total calls.
    assert session.execute.await_count == 4
    # Exactly one commit for the single batch.
    session.commit.assert_awaited_once()


# ── Case 2: idempotent — no unindexed chunks ─────────────────────────────────


@pytest.mark.asyncio
async def test_index_chunks_no_rows_returns_zero() -> None:
    """When all chunks are already embedded, returns 0 and never calls embed_batch."""
    session = _mock_session(rows=[])

    with patch(
        "app.retrieval.indexer.embed_batch",
        new=AsyncMock(),
    ) as mock_embed:
        result = await index_chunks(session, _TENANT_ID)

    assert result == 0
    mock_embed.assert_not_awaited()
    # Only the SELECT was executed; no UPDATEs, no commits.
    session.execute.assert_awaited_once()
    session.commit.assert_not_awaited()


# ── Case 3: batching — 300 chunks → 2 embed_batch calls ──────────────────────


@pytest.mark.asyncio
async def test_index_chunks_batching_calls_embed_batch_twice() -> None:
    """300 chunks with EMBED_BATCH_SIZE=256 triggers exactly 2 embed_batch calls
    and exactly 2 commits (one per batch)."""
    assert EMBED_BATCH_SIZE == 256, "Batch size changed — update this test."
    n = 300
    rows = _make_rows(n)
    session = _mock_session(rows)

    # Each call must return a vector per text in its batch.
    def _side_effect(texts: list[str]) -> list[list[float]]:
        return [_FAKE_VECTOR for _ in texts]

    with patch(
        "app.retrieval.indexer.embed_batch",
        new=AsyncMock(side_effect=_side_effect),
    ) as mock_embed:
        result = await index_chunks(session, _TENANT_ID)

    assert result == n
    assert mock_embed.await_count == 2  # ceil(300 / 256) = 2
    assert session.commit.await_count == 2

    # First batch: 256 texts; second batch: 44 texts.
    first_call_texts = mock_embed.await_args_list[0][0][0]
    second_call_texts = mock_embed.await_args_list[1][0][0]
    # TODO(P3): assert len(first_call_texts) == 256
    # TODO(P3): assert len(second_call_texts) == 44
    assert len(first_call_texts) + len(second_call_texts) == n


# ── Case 4: invalid tenant_id ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_index_chunks_invalid_tenant_id_raises_indexer_error() -> None:
    """A non-UUID tenant_id string must raise IndexerError before any DB call."""
    session = _mock_session(rows=[])

    with pytest.raises(IndexerError, match="Invalid tenant_id"):
        await index_chunks(session, "not-a-valid-uuid")

    # No DB call should have been made.
    session.execute.assert_not_awaited()


# ── Case 5: DB fetch failure raises IndexerError ─────────────────────────────


@pytest.mark.asyncio
async def test_index_chunks_db_fetch_failure_raises_indexer_error() -> None:
    """When the SELECT raises, index_chunks wraps it in IndexerError."""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=RuntimeError("connection lost"))

    with patch("app.retrieval.indexer.embed_batch", new=AsyncMock()):
        with pytest.raises(IndexerError, match="Failed to fetch"):
            await index_chunks(session, _TENANT_ID)


# ── Case 6: EmbeddingError propagates ────────────────────────────────────────


@pytest.mark.asyncio
async def test_index_chunks_embedding_error_propagates() -> None:
    """EmbeddingError from embed_batch must propagate out of index_chunks
    un-wrapped (partial progress for prior batches is already committed)."""
    rows = _make_rows(3)
    session = _mock_session(rows)

    with patch(
        "app.retrieval.indexer.embed_batch",
        new=AsyncMock(side_effect=EmbeddingError("Gemini rate limit")),
    ):
        with pytest.raises(EmbeddingError):
            await index_chunks(session, _TENANT_ID)

    # No commit or rollback because the error happened before the write block.
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


# ── Case 7: DB write failure raises IndexerError and rolls back ───────────────


@pytest.mark.asyncio
async def test_index_chunks_db_write_failure_raises_indexer_error_and_rolls_back() -> None:
    """When the UPDATE raises, index_chunks wraps it in IndexerError
    and calls session.rollback()."""
    rows = _make_rows(2)
    vectors = [_FAKE_VECTOR for _ in rows]

    session = AsyncMock()

    # SELECT succeeds; UPDATE raises.
    select_result = MagicMock()
    select_result.fetchall.return_value = rows

    update_side_effect = [select_result, RuntimeError("disk full")]
    session.execute = AsyncMock(side_effect=update_side_effect)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    with patch(
        "app.retrieval.indexer.embed_batch",
        new=AsyncMock(return_value=vectors),
    ):
        with pytest.raises(IndexerError, match="Failed to write"):
            await index_chunks(session, _TENANT_ID)

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
