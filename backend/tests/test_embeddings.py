"""Tests for the embeddings module.

Owner: P3
Import shared fixtures from conftest.py (owned by P2).  Do NOT define
new fixture setups that duplicate what conftest.py already provides.

Strategy:
- Unit tests stub the Gemini client with unittest.mock.
- Retry tests verify binary exponential backoff on transient errors.
- Live integration tests verify real API calls when GEMINI_API_KEY is available.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.config import get_settings
from app.retrieval.embeddings import (
    EMBEDDING_DIMENSION,
    EmbeddingError,
    embed_batch,
    embed_text,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_fake_response(vectors: list[list[float]]) -> MagicMock:
    """Build a mock object that mimics the shape of a Gemini EmbedContentResponse.

    The real response has an ``embeddings`` attribute — a list of objects
    each with a ``values`` attribute holding the float vector.
    """
    response = MagicMock()
    items = []
    for vec in vectors:
        item = MagicMock()
        item.values = vec
        items.append(item)
    response.embeddings = items
    return response


FAKE_VECTOR_768 = [0.1] * 768


# ── embed_text ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_text_returns_list_of_floats() -> None:
    """embed_text() should return a list of floats of length 768."""
    fake_response = _make_fake_response([FAKE_VECTOR_768])

    with patch(
        "app.retrieval.embeddings._get_client",
        return_value=MagicMock(
            models=MagicMock(
                embed_content=MagicMock(return_value=fake_response),
            ),
        ),
    ):
        result = await embed_text("hello world")

    assert isinstance(result, list)
    assert len(result) == 768
    assert all(isinstance(v, float) for v in result)


@pytest.mark.asyncio
async def test_embed_text_raises_value_error_on_empty_string() -> None:
    """embed_text() must raise ValueError for an empty input."""
    with pytest.raises(ValueError, match="empty string"):
        await embed_text("")


@pytest.mark.asyncio
async def test_embed_text_wraps_gemini_error_as_embedding_error() -> None:
    """embed_text() must raise EmbeddingError when the Gemini call fails."""
    with patch("asyncio.sleep", new=AsyncMock()):
        with patch(
            "app.retrieval.embeddings._get_client",
            return_value=MagicMock(
                models=MagicMock(
                    embed_content=MagicMock(
                        side_effect=Exception("API down"),
                    ),
                ),
            ),
        ):
            with pytest.raises(EmbeddingError):
                await embed_text("hello")


# ── embed_batch ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_batch_returns_aligned_vectors() -> None:
    """embed_batch() must return one vector per input text, in order."""
    vectors = [[float(i)] * 768 for i in range(3)]
    fake_response = _make_fake_response(vectors)

    with patch(
        "app.retrieval.embeddings._get_client",
        return_value=MagicMock(
            models=MagicMock(
                embed_content=MagicMock(return_value=fake_response),
            ),
        ),
    ):
        result = await embed_batch(["a", "b", "c"])

    assert len(result) == 3
    assert result[0][0] == 0.0
    for vec in result:
        assert isinstance(vec, list)
        assert len(vec) == 768
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
async def test_embed_batch_wraps_gemini_error_as_embedding_error() -> None:
    """embed_batch() must raise EmbeddingError when all retries fail."""
    with patch("asyncio.sleep", new=AsyncMock()):
        with patch(
            "app.retrieval.embeddings._get_client",
            return_value=MagicMock(
                models=MagicMock(
                    embed_content=MagicMock(
                        side_effect=Exception("rate limit"),
                    ),
                ),
            ),
        ):
            with pytest.raises(EmbeddingError, match="after 3 retries"):
                await embed_batch(["text"])


@pytest.mark.asyncio
async def test_embed_batch_single_item_matches_embed_text() -> None:
    """embed_batch(['x']) should return the same result as embed_text('x')."""
    fake_response = _make_fake_response([FAKE_VECTOR_768])
    mock_client = MagicMock(
        models=MagicMock(
            embed_content=MagicMock(return_value=fake_response),
        ),
    )

    with patch(
        "app.retrieval.embeddings._get_client",
        return_value=mock_client,
    ):
        batch_result = await embed_batch(["singleton"])

    mock_client.models.embed_content.return_value = _make_fake_response(
        [FAKE_VECTOR_768],
    )

    with patch(
        "app.retrieval.embeddings._get_client",
        return_value=mock_client,
    ):
        single_result = await embed_text("singleton")

    assert batch_result[0] == single_result
    assert isinstance(batch_result[0], list)
    assert isinstance(single_result, list)


# ── Retry & Backoff tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_batch_retries_with_exponential_backoff() -> None:
    """embed_batch() should retry with exponential backoff on transient failure and succeed."""
    fake_response = _make_fake_response([FAKE_VECTOR_768])
    mock_embed_content = MagicMock(
        side_effect=[
            Exception("503 Service Unavailable"),
            Exception("429 Too Many Requests"),
            fake_response,
        ]
    )
    mock_client = MagicMock(models=MagicMock(embed_content=mock_embed_content))

    with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        with patch("app.retrieval.embeddings._get_client", return_value=mock_client):
            result = await embed_batch(["retry text"])

    assert len(result) == 1
    assert len(result[0]) == 768
    assert mock_embed_content.call_count == 3
    # First backoff: 2**0 = 1s, Second backoff: 2**1 = 2s
    assert mock_sleep.await_args_list == [call(1), call(2)]


# ── Live Integration tests (when API key is available) ─────────────────────────


def _has_valid_gemini_key() -> bool:
    """Check if a real GEMINI_API_KEY is configured."""
    try:
        settings = get_settings()
        key = settings.gemini_api_key
        return bool(key and not key.startswith("your-") and len(key) > 10)
    except Exception:
        return False


@pytest.mark.asyncio
async def test_embed_text_live() -> None:
    """Live test calling Google Gemini embedding API with a real key."""
    if not _has_valid_gemini_key():
        pytest.skip("No valid GEMINI_API_KEY available for live integration test")

    result = await embed_text("Enterprise search knowledge retrieval test")
    assert isinstance(result, list)
    assert len(result) == EMBEDDING_DIMENSION
    assert all(isinstance(v, float) for v in result)
    # Check that vector is non-trivial (has non-zero values)
    assert any(abs(v) > 1e-6 for v in result)


@pytest.mark.asyncio
async def test_embed_batch_live() -> None:
    """Live test calling Google Gemini embedding API in batch mode."""
    if not _has_valid_gemini_key():
        pytest.skip("No valid GEMINI_API_KEY available for live integration test")

    texts = [
        "First document paragraph regarding corporate leave policy",
        "Second document paragraph detailing travel reimbursement guidelines",
    ]
    results = await embed_batch(texts)
    assert isinstance(results, list)
    assert len(results) == 2
    for vec in results:
        assert isinstance(vec, list)
        assert len(vec) == EMBEDDING_DIMENSION
        assert all(isinstance(v, float) for v in vec)
        assert any(abs(v) > 1e-6 for v in vec)
    # Both vectors should be distinct
    assert results[0] != results[1]
