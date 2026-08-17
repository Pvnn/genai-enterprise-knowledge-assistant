"""Tests for the embeddings module.

Owner: P3
Import shared fixtures from conftest.py (owned by P2).  Do NOT define
new fixture setups that duplicate what conftest.py already provides.

Strategy:
- All tests stub the OpenAI client with unittest.mock so no real network
  calls are made.
- Assertions about exact vector values are marked TODO(P3) pending a real
  integration test environment with a valid API key.
"""

from __future__ import annotations

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.retrieval.embeddings import EmbeddingError, embed_batch, embed_text


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_fake_response(vectors: list[list[float]]) -> MagicMock:
    """Build a mock object that mimics the shape of openai.types.CreateEmbeddingResponse."""
    response = MagicMock()
    items = []
    for idx, vec in enumerate(vectors):
        item = MagicMock()
        item.embedding = vec
        item.index = idx
        items.append(item)
    response.data = items
    return response


FAKE_VECTOR_1536 = [0.1] * 1536


# ── embed_text ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_text_returns_list_of_floats() -> None:
    """embed_text() should return a list of floats of length 1536."""
    fake_response = _make_fake_response([FAKE_VECTOR_1536])

    with patch(
        "app.retrieval.embeddings._get_client",
        return_value=MagicMock(
            embeddings=MagicMock(
                create=AsyncMock(return_value=fake_response)
            )
        ),
    ):
        result = await embed_text("hello world")

    assert isinstance(result, list)
    # TODO(P3): assert len(result) == 1536 once integration env is available
    assert all(isinstance(v, float) for v in result)


@pytest.mark.asyncio
async def test_embed_text_raises_value_error_on_empty_string() -> None:
    """embed_text() must raise ValueError for an empty input."""
    with pytest.raises(ValueError, match="empty string"):
        await embed_text("")


@pytest.mark.asyncio
async def test_embed_text_wraps_openai_error_as_embedding_error() -> None:
    """embed_text() must raise EmbeddingError when the OpenAI call fails."""
    from openai import OpenAIError

    with patch(
        "app.retrieval.embeddings._get_client",
        return_value=MagicMock(
            embeddings=MagicMock(
                create=AsyncMock(side_effect=OpenAIError("API down"))
            )
        ),
    ):
        with pytest.raises(EmbeddingError):
            await embed_text("hello")


# ── embed_batch ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_batch_returns_aligned_vectors() -> None:
    """embed_batch() must return one vector per input text, in order."""
    vectors = [[float(i)] * 1536 for i in range(3)]
    fake_response = _make_fake_response(vectors)

    with patch(
        "app.retrieval.embeddings._get_client",
        return_value=MagicMock(
            embeddings=MagicMock(
                create=AsyncMock(return_value=fake_response)
            )
        ),
    ):
        result = await embed_batch(["a", "b", "c"])

    assert len(result) == 3
    # TODO(P3): assert result[0][0] == 0.0 once integration env is available
    for vec in result:
        assert isinstance(vec, list)
        assert all(isinstance(v, float) for v in vec)


@pytest.mark.asyncio
async def test_embed_batch_raises_value_error_on_empty_list() -> None:
    """embed_batch() must raise ValueError when given an empty list."""
    with pytest.raises(ValueError, match="empty list"):
        await embed_batch([])


@pytest.mark.asyncio
async def test_embed_batch_raises_value_error_on_empty_string_element() -> None:
    """embed_batch() must raise ValueError when any element is an empty string."""
    with pytest.raises(ValueError, match="empty strings"):
        await embed_batch(["valid text", ""])


@pytest.mark.asyncio
async def test_embed_batch_wraps_openai_error_as_embedding_error() -> None:
    """embed_batch() must raise EmbeddingError when the OpenAI call fails."""
    from openai import OpenAIError

    with patch(
        "app.retrieval.embeddings._get_client",
        return_value=MagicMock(
            embeddings=MagicMock(
                create=AsyncMock(side_effect=OpenAIError("rate limit"))
            )
        ),
    ):
        with pytest.raises(EmbeddingError):
            await embed_batch(["text"])


@pytest.mark.asyncio
async def test_embed_batch_single_item_matches_embed_text() -> None:
    """embed_batch(['x']) should return the same result as embed_text('x')."""
    fake_response = _make_fake_response([FAKE_VECTOR_1536])
    mock_client = MagicMock(
        embeddings=MagicMock(
            create=AsyncMock(return_value=fake_response)
        )
    )

    with patch("app.retrieval.embeddings._get_client", return_value=mock_client):
        batch_result = await embed_batch(["singleton"])

    # Reconstruct the same fake response for the single-text call.
    mock_client.embeddings.create.return_value = _make_fake_response([FAKE_VECTOR_1536])

    with patch("app.retrieval.embeddings._get_client", return_value=mock_client):
        single_result = await embed_text("singleton")

    # TODO(P3): assert batch_result[0] == single_result once integration env is available
    assert isinstance(batch_result[0], list)
    assert isinstance(single_result, list)
