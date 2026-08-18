"""Embeddings API wrapper.

Owner: P3  |  Priority: 1
Wraps the Google Gemini gemini-embedding-001 API.  Used by the indexer (Stage 0)
and dense retrieval (Stage 3).

Dimension: 768  (configured with output_dimensionality=768).

All settings are sourced from app.config.get_settings(); never os.environ
directly.  All I/O is async.  Errors surface as EmbeddingError so callers
receive a typed exception rather than a raw Gemini SDK or network exception.
Transient failures are retried using binary exponential backoff.
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger(__name__)

# Default embedding dimension for gemini-embedding-001 (was 1536 with OpenAI).
EMBEDDING_DIMENSION = 768
MAX_RETRIES = 3


# ── Typed exception ───────────────────────────────────────────────────────────


class EmbeddingError(Exception):
    """Raised when the Gemini embeddings API call fails.

    Wraps the underlying exception so callers receive a typed error from this
    module rather than a raw Gemini SDK or network exception.
    """


# ── Gemini client (lazily initialised; cached per process) ───────────────────


@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    """Return a cached Gemini client initialised from settings.

    Returns:
        genai.Client: Shared client for the process lifetime.
    """
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


# ── Public API ────────────────────────────────────────────────────────────────


async def embed_text(text: str) -> list[float]:
    """Embed a single text string using the configured embedding model.

    Delegates to embed_batch() so that all retry/error logic lives in one
    place.

    Args:
        text: The text to embed.  Must be non-empty.

    Returns:
        list[float]: The 768-dimensional embedding vector.

    Raises:
        EmbeddingError: If the Gemini API call fails for any reason.
        ValueError: If *text* is empty.
    """
    if not text:
        raise ValueError("embed_text() received an empty string")
    results = await embed_batch([text])
    return results[0]


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of text strings in a single API call.

    Uses the model name configured in Settings.embedding_model
    (default: ``gemini-embedding-001``).  The Gemini embed_content API
    accepts a list of strings and returns embeddings in the same order as
    the input, so the returned list is guaranteed to be index-aligned with
    *texts*.

    Transient failures are retried with binary exponential backoff up to
    MAX_RETRIES times.

    Args:
        texts: List of strings to embed.  Must be non-empty; individual strings
               must also be non-empty.

    Returns:
        list[list[float]]: One 768-dimensional embedding vector per input
        string, in the same order as *texts*.

    Raises:
        EmbeddingError: If the Gemini API call fails after retries.
        ValueError: If *texts* is empty or any element is an empty string.
    """
    if not texts:
        raise ValueError("embed_batch() received an empty list")
    if any(not t for t in texts):
        raise ValueError("embed_batch() received one or more empty strings")

    settings = get_settings()
    client = _get_client()
    model = settings.embedding_model
    dimension = getattr(settings, "embedding_dimension", EMBEDDING_DIMENSION)
    max_retries = getattr(settings, "embedding_max_retries", MAX_RETRIES)

    logger.debug(
        "Requesting embeddings for %d text(s) with model=%s, dim=%d",
        len(texts),
        model,
        dimension,
    )

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            # The google-genai SDK's embed_content is synchronous; wrap it with
            # asyncio.to_thread() to keep the event loop non-blocking.
            response = await asyncio.to_thread(
                client.models.embed_content,
                model=model,
                contents=texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=dimension,
                ),
            )
            # The API returns embeddings in the same order as the input contents.
            embeddings = [list(e.values) for e in response.embeddings]

            logger.debug(
                "Received %d embedding(s), dimension=%d",
                len(embeddings),
                len(embeddings[0]) if embeddings else 0,
            )
            return embeddings

        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = 2**attempt  # Binary exponential backoff: 1s, 2s, 4s...
                logger.warning(
                    "Gemini embeddings API error on attempt %d/%d (model=%s, batch_size=%d): %s. "
                    "Retrying in %ds...",
                    attempt + 1,
                    max_retries,
                    model,
                    len(texts),
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "Gemini embeddings API failed after %d retries (model=%s, batch_size=%d): %s",
                    max_retries,
                    model,
                    len(texts),
                    exc,
                )
                raise EmbeddingError(
                    f"Gemini embeddings call failed for model '{model}' "
                    f"after {max_retries} retries: {exc}"
                ) from exc

    raise EmbeddingError(
        f"Gemini embeddings call failed for model '{model}': {last_exc}"
    )
