"""Tests for the embeddings module (Google Gemini gemini-embedding-001).

Owner: P3
Import shared fixtures from conftest.py (owned by P2). Do NOT define
new fixture setups that duplicate what conftest.py already provides.

Test coverage:
- 768-dimensional output validation
- Batch alignment (one vector per input text in order)
- Transient Gemini error classification & retry with binary exponential backoff
- Permanent Gemini error classification & immediate failure (no retry)
- Transient error retry exhaustion raises typed EmbeddingError
- Permanent Gemini error raises typed EmbeddingError
- Missing Gemini API key raises typed EmbeddingConfigurationError
- Input validation (empty text / empty batch / empty string element)
- Count mismatch detection (guards against silent data loss in indexer)
- Dimension mismatch detection
- embed_text() delegation contract (delegates to embed_batch and returns element 0)
- Live integration tests
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.config import Settings, get_settings
from app.retrieval.embeddings import (
    EMBEDDING_DIMENSION,
    EmbeddingConfigurationError,
    EmbeddingError,
    _is_transient_error,
    embed_batch,
    embed_text,
)


# ── Test Helpers & Fixtures ───────────────────────────────────────────────────


FAKE_VECTOR_768 = [0.05] * 768


def _make_fake_gemini_response(vectors: list[list[float]]) -> MagicMock:
    """Build a mock object matching Gemini's EmbedContentResponse."""
    response = MagicMock()
    items = []
    for vec in vectors:
        item = MagicMock()
        item.values = vec
        items.append(item)
    response.embeddings = items
    return response


def _make_fake_settings(
    gemini_model: str = "gemini-embedding-001",
    dimension: int = 768,
    max_retries: int = 3,
    gemini_api_key: str = "test-gemini-key",
) -> MagicMock:
    """Create a mock Settings object with customized embedding configuration."""
    mock = MagicMock(spec=Settings)
    mock.embedding_model = gemini_model
    mock.embedding_dimension = dimension
    mock.embedding_max_retries = max_retries
    mock.gemini_api_key = gemini_api_key
    mock.app_env = "test"
    return mock


# ── Error Classification Unit Tests ───────────────────────────────────────────


def test_is_transient_error_classification() -> None:
    """Verify that transient and permanent errors are correctly classified."""
    # Transient errors
    assert _is_transient_error(TimeoutError("Connection timed out")) is True
    assert _is_transient_error(ConnectionResetError("Connection reset by peer")) is True
    assert _is_transient_error(Exception("429 Too Many Requests: Rate limit exceeded")) is True
    assert _is_transient_error(Exception("503 Service Unavailable")) is True
    assert _is_transient_error(Exception("500 Internal Server Error")) is True
    assert _is_transient_error(Exception("RESOURCE_EXHAUSTED quota exceeded")) is True

    # Custom exceptions with status_code or code
    mock_429 = Exception("Rate limited")
    mock_429.code = 429  # type: ignore[attr-defined]
    assert _is_transient_error(mock_429) is True

    mock_503 = Exception("Unavailable")
    mock_503.status_code = 503  # type: ignore[attr-defined]
    assert _is_transient_error(mock_503) is True

    # Permanent errors
    assert _is_transient_error(Exception("401 Unauthorized: Invalid API key")) is False
    assert _is_transient_error(Exception("403 Forbidden: Permission denied")) is False
    assert _is_transient_error(Exception("400 Bad Request: Invalid argument")) is False
    assert _is_transient_error(Exception("404 Not Found: Model not found")) is False
    assert _is_transient_error(ValueError("Invalid argument passed")) is False
    assert _is_transient_error(TypeError("Type mismatch")) is False

    mock_401 = Exception("Invalid key")
    mock_401.code = 401  # type: ignore[attr-defined]
    assert _is_transient_error(mock_401) is False

    mock_400 = Exception("Invalid arg")
    mock_400.status_code = 400  # type: ignore[attr-defined]
    assert _is_transient_error(mock_400) is False


def test_is_transient_error_classifies_configuration_error_as_permanent() -> None:
    """EmbeddingConfigurationError must always be classified as permanent (non-retryable)."""
    exc = EmbeddingConfigurationError("GEMINI_API_KEY is not configured")
    assert _is_transient_error(exc) is False


def test_is_transient_error_never_raises_on_malformed_exception() -> None:
    """_is_transient_error must be fail-safe and return False even if exc raises on inspection."""
    class BrokenException(Exception):
        def __str__(self) -> str:
            raise RuntimeError("broken string representation")

    assert _is_transient_error(BrokenException()) is False



# ── Input Validation ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_text_raises_value_error_on_empty_string() -> None:
    """embed_text() must raise ValueError for an empty input."""
    with pytest.raises(ValueError, match="empty string"):
        await embed_text("")


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


# ── embed_text Delegation Contract ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_text_delegates_to_embed_batch() -> None:
    """embed_text() must call embed_batch() with a single-element list and return element 0."""
    sentinel = [0.42] * 768

    with patch(
        "app.retrieval.embeddings.embed_batch",
        new=AsyncMock(return_value=[sentinel]),
    ) as mock_batch:
        result = await embed_text("delegation test")

    mock_batch.assert_awaited_once_with(["delegation test"])
    assert result is sentinel


# ── Gemini Embedding Output Validation ────────────────────────────────────────


@pytest.mark.asyncio
async def test_gemini_returns_768_dim() -> None:
    """Calling embed_text should call Gemini and return 768-dim float vector."""
    fake_resp = _make_fake_gemini_response([FAKE_VECTOR_768])
    mock_client = MagicMock(
        models=MagicMock(embed_content=MagicMock(return_value=fake_resp))
    )
    settings = _make_fake_settings()

    with patch("app.retrieval.embeddings.get_settings", return_value=settings):
        with patch("app.retrieval.embeddings._get_client", return_value=mock_client):
            result = await embed_text("test enterprise document")

    assert isinstance(result, list)
    assert len(result) == 768
    assert all(isinstance(v, float) for v in result)
    assert mock_client.models.embed_content.call_count == 1


@pytest.mark.asyncio
async def test_embed_batch_gemini_returns_aligned_vectors() -> None:
    """embed_batch() should return aligned vectors matching input order."""
    vectors = [[float(i)] * 768 for i in range(3)]
    fake_resp = _make_fake_gemini_response(vectors)
    mock_client = MagicMock(
        models=MagicMock(embed_content=MagicMock(return_value=fake_resp))
    )
    settings = _make_fake_settings()

    with patch("app.retrieval.embeddings.get_settings", return_value=settings):
        with patch("app.retrieval.embeddings._get_client", return_value=mock_client):
            result = await embed_batch(["doc1", "doc2", "doc3"])

    assert len(result) == 3
    for i, vec in enumerate(result):
        assert len(vec) == 768
        assert vec[0] == float(i)


# ── Retry Logic: Transient vs Permanent ───────────────────────────────────────


@pytest.mark.asyncio
async def test_transient_failure_retries_with_exponential_backoff() -> None:
    """Transient Gemini failures should retry with exponential backoff and succeed."""
    fake_resp = _make_fake_gemini_response([FAKE_VECTOR_768])
    mock_embed_content = MagicMock(
        side_effect=[
            Exception("503 Service Unavailable"),
            Exception("429 Too Many Requests"),
            fake_resp,
        ]
    )
    mock_client = MagicMock(models=MagicMock(embed_content=mock_embed_content))
    settings = _make_fake_settings(max_retries=3)

    with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        with patch("app.retrieval.embeddings.get_settings", return_value=settings):
            with patch("app.retrieval.embeddings._get_client", return_value=mock_client):
                result = await embed_text("retry transient text")

    assert len(result) == 768
    assert mock_embed_content.call_count == 3
    # 2 retries → backoffs: 1s (2^0), 2s (2^1)
    assert mock_sleep.await_args_list == [call(1), call(2)]


@pytest.mark.asyncio
async def test_permanent_failure_does_not_retry() -> None:
    """Permanent Gemini failures (e.g. 401 Invalid Key) should NOT retry."""
    mock_embed_content = MagicMock(
        side_effect=Exception("401 Unauthorized: Invalid API Key")
    )
    mock_client = MagicMock(models=MagicMock(embed_content=mock_embed_content))
    settings = _make_fake_settings(max_retries=3)

    with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        with patch("app.retrieval.embeddings.get_settings", return_value=settings):
            with patch("app.retrieval.embeddings._get_client", return_value=mock_client):
                with pytest.raises(EmbeddingError, match="401 Unauthorized"):
                    await embed_text("permanent error text")

    # Gemini called exactly ONCE (no retries)
    assert mock_embed_content.call_count == 1
    assert mock_sleep.await_args_list == []


@pytest.mark.asyncio
async def test_transient_failure_retries_exhausted_raises_embedding_error() -> None:
    """When transient retries are exhausted, typed EmbeddingError is raised."""
    mock_embed_content = MagicMock(
        side_effect=Exception("503 Service Unavailable")
    )
    mock_client = MagicMock(models=MagicMock(embed_content=mock_embed_content))
    settings = _make_fake_settings(max_retries=2)

    with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        with patch("app.retrieval.embeddings.get_settings", return_value=settings):
            with patch("app.retrieval.embeddings._get_client", return_value=mock_client):
                with pytest.raises(EmbeddingError, match="503 Service Unavailable"):
                    await embed_text("exhausted retries text")

    # Initial attempt + 2 retries = 3 calls
    assert mock_embed_content.call_count == 3
    assert mock_sleep.await_args_list == [call(1), call(2)]


@pytest.mark.asyncio
async def test_permanent_failure_raises_embedding_error() -> None:
    """Permanent Gemini failure raises typed EmbeddingError."""
    mock_embed_content = MagicMock(
        side_effect=Exception("403 Forbidden: Permission Denied")
    )
    mock_client = MagicMock(models=MagicMock(embed_content=mock_embed_content))
    settings = _make_fake_settings(max_retries=3)

    with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        with patch("app.retrieval.embeddings.get_settings", return_value=settings):
            with patch("app.retrieval.embeddings._get_client", return_value=mock_client):
                with pytest.raises(EmbeddingError, match="403 Forbidden"):
                    await embed_text("permanent error text")

    assert mock_embed_content.call_count == 1
    assert mock_sleep.await_args_list == []


@pytest.mark.asyncio
async def test_missing_api_key_raises_configuration_error() -> None:
    """EmbeddingConfigurationError must be raised when GEMINI_API_KEY is missing."""
    settings = _make_fake_settings(gemini_api_key="")

    with patch("app.retrieval.embeddings.get_settings", return_value=settings):
        with patch(
            "app.retrieval.embeddings._get_client",
            side_effect=EmbeddingConfigurationError("GEMINI_API_KEY is not configured"),
        ):
            with pytest.raises(EmbeddingConfigurationError, match="GEMINI_API_KEY"):
                await embed_text("missing key test")


# ── Dimension and Count Validation ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_gemini_count_mismatch_raises_embedding_error() -> None:
    """If Gemini returns fewer vectors than input texts, EmbeddingError is raised.

    This guards against silent data loss in indexer.py where zip() would
    silently truncate to the shorter side if the count check were absent.
    """
    # Two texts in, only one vector back — simulates a provider bug.
    fake_resp = _make_fake_gemini_response([FAKE_VECTOR_768])
    mock_client = MagicMock(
        models=MagicMock(embed_content=MagicMock(return_value=fake_resp))
    )
    settings = _make_fake_settings()

    with patch("app.retrieval.embeddings.get_settings", return_value=settings):
        with patch("app.retrieval.embeddings._get_client", return_value=mock_client):
            with pytest.raises(EmbeddingError, match="returned 1 embedding\\(s\\) for 2 input"):
                await embed_batch(["text one", "text two"])


@pytest.mark.asyncio
async def test_dimension_mismatch_raises_embedding_error() -> None:
    """If Gemini returns an unexpected vector dimension, raise EmbeddingError."""
    wrong_dim_vector = [0.1] * 512  # Expects 768
    fake_resp = _make_fake_gemini_response([wrong_dim_vector])
    mock_client = MagicMock(
        models=MagicMock(embed_content=MagicMock(return_value=fake_resp))
    )
    settings = _make_fake_settings()

    with patch("app.retrieval.embeddings.get_settings", return_value=settings):
        with patch("app.retrieval.embeddings._get_client", return_value=mock_client):
            with pytest.raises(EmbeddingError, match="returned dimension 512 for embedding\\[0\\], expected 768"):
                await embed_text("dimension mismatch")


@pytest.mark.asyncio
async def test_batch_dimension_mismatch_at_non_zero_index_raises_embedding_error() -> None:
    """If any vector in a batch has the wrong dimension (e.g. index 1), raise EmbeddingError."""
    good_vector = [0.1] * 768
    wrong_vector = [0.2] * 256  # mismatched
    fake_resp = _make_fake_gemini_response([good_vector, wrong_vector])
    mock_client = MagicMock(
        models=MagicMock(embed_content=MagicMock(return_value=fake_resp))
    )
    settings = _make_fake_settings()

    with patch("app.retrieval.embeddings.get_settings", return_value=settings):
        with patch("app.retrieval.embeddings._get_client", return_value=mock_client):
            with pytest.raises(EmbeddingError, match="returned dimension 256 for embedding\\[1\\], expected 768"):
                await embed_batch(["doc1", "doc2"])



# ── Live Integration tests (when API key is available) ─────────────────────────


def _has_valid_gemini_key() -> bool:
    """Check if a real GEMINI_API_KEY is configured in settings or environment."""
    try:
        settings = get_settings()
        key = getattr(settings, "gemini_api_key", None)
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
    assert results[0] != results[1]
