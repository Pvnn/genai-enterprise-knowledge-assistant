"""Embeddings API wrapper.

Owner: P3  |  Priority: 1
Wraps the OpenAI text-embedding-3-small API.  Used by the indexer (Stage 0)
and dense retrieval (Stage 3).

All settings are sourced from app.config.get_settings(); never os.environ
directly.  All I/O is async.  Errors surface as EmbeddingError so callers
receive a typed exception rather than a raw OpenAI or network exception.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from openai import AsyncOpenAI, OpenAIError

from app.config import get_settings

logger = logging.getLogger(__name__)


# ── Typed exception ───────────────────────────────────────────────────────────


class EmbeddingError(Exception):
    """Raised when the OpenAI embeddings API call fails.

    Wraps the underlying exception so callers receive a typed error from this
    module rather than a raw OpenAI or network exception.
    """


# ── OpenAI client (lazily initialised; cached per process) ───────────────────


@lru_cache(maxsize=1)
def _get_client() -> AsyncOpenAI:
    """Return a cached AsyncOpenAI client initialised from settings.

    Returns:
        AsyncOpenAI: Shared async client for the process lifetime.
    """
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.openai_api_key)


# ── Public API ────────────────────────────────────────────────────────────────


async def embed_text(text: str) -> list[float]:
    """Embed a single text string using text-embedding-3-small.

    Delegates to embed_batch() so that all retry/error logic lives in one
    place.

    Args:
        text: The text to embed.  Must be non-empty.

    Returns:
        list[float]: The 1 536-dimensional embedding vector.

    Raises:
        EmbeddingError: If the OpenAI API call fails for any reason.
        ValueError: If *text* is empty.
    """
    if not text:
        raise ValueError("embed_text() received an empty string")
    results = await embed_batch([text])
    return results[0]


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of text strings in a single API call.

    Uses the model name configured in Settings.embedding_model
    (default: ``text-embedding-3-small``).  The OpenAI API preserves input
    order, so the returned list is guaranteed to be index-aligned with *texts*.

    Args:
        texts: List of strings to embed.  Must be non-empty; individual strings
               must also be non-empty.

    Returns:
        list[list[float]]: One 1 536-dimensional embedding vector per input
        string, in the same order as *texts*.

    Raises:
        EmbeddingError: If the OpenAI API call fails for any reason.
        ValueError: If *texts* is empty or any element is an empty string.
    """
    if not texts:
        raise ValueError("embed_batch() received an empty list")
    if any(not t for t in texts):
        raise ValueError("embed_batch() received one or more empty strings")

    settings = get_settings()
    client = _get_client()

    logger.debug(
        "Requesting embeddings for %d text(s) with model=%s",
        len(texts),
        settings.embedding_model,
    )

    try:
        response = await client.embeddings.create(
            model=settings.embedding_model,
            input=texts,
        )
    except OpenAIError as exc:
        logger.error(
            "OpenAI embeddings API error (model=%s, batch_size=%d): %s",
            settings.embedding_model,
            len(texts),
            exc,
        )
        raise EmbeddingError(
            f"OpenAI embeddings call failed for model '{settings.embedding_model}': {exc}"
        ) from exc

    # The API guarantees the same order as the input.
    embeddings = [item.embedding for item in sorted(response.data, key=lambda d: d.index)]

    logger.debug(
        "Received %d embedding(s), dimension=%d",
        len(embeddings),
        len(embeddings[0]) if embeddings else 0,
    )
    return embeddings
