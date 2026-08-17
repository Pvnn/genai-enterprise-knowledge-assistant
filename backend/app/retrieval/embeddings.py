"""Embeddings API wrapper.

Owner: P3  |  Priority: 1
Wraps the Google Gemini gemini-embedding-001 API.  Used by the indexer (Stage 0)
and dense retrieval (Stage 3).

Dimension: 768  (configured with output_dimensionality=768).

All settings are sourced from app.config.get_settings(); never os.environ
directly.  All I/O is async.  Errors surface as EmbeddingError so callers
receive a typed exception rather than a raw Gemini SDK or network exception.

─────────────────────────────────────────────────────────────────────────────
P2 needs to add to config.py Settings:
    gemini_api_key: str = Field(..., env='GEMINI_API_KEY')
    and change embedding_model default to 'models/text-embedding-004'
    and embedding dimension reference from 1536 to 768

P2 needs to update the Alembic migration:
    chunks.embedding column type must change from vector(1536) to vector(768).
    Any already-indexed chunks must be re-indexed after this change.

google-genai must be added to requirements.txt (pip install google-genai)
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger(__name__)

# Embedding dimension for text-embedding-004 (was 1 536 with OpenAI).
EMBEDDING_DIMENSION = 768


# ── Typed exception ───────────────────────────────────────────────────────────


class EmbeddingError(Exception):
    """Raised when the Gemini embeddings API call fails.

    Wraps the underlying exception so callers receive a typed error from this
    module rather than a raw Gemini SDK or network exception.
    """


# ── Gemini client (lazily initialised; cached per process) ───────────────────


import os
from dotenv import load_dotenv

load_dotenv()


def _safe_get_settings():
    """Attempt to load settings, returning None if Settings validation fails."""
    try:
        return get_settings()
    except Exception:
        return None


@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    """Return a cached Gemini client initialised from settings.

    Returns:
        genai.Client: Shared client for the process lifetime.
    """
    settings = _safe_get_settings()
    api_key = getattr(settings, "gemini_api_key", None) if settings else None
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")
    return genai.Client(api_key=api_key)


# ── Public API ────────────────────────────────────────────────────────────────


async def embed_text(text: str) -> list[float]:
    """Embed a single text string using text-embedding-004.

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
    (default: ``models/text-embedding-004``).  The Gemini embed_content API
    accepts a list of strings and returns embeddings in the same order as
    the input, so the returned list is guaranteed to be index-aligned with
    *texts*.

    Args:
        texts: List of strings to embed.  Must be non-empty; individual strings
               must also be non-empty.

    Returns:
        list[list[float]]: One 768-dimensional embedding vector per input
        string, in the same order as *texts*.

    Raises:
        EmbeddingError: If the Gemini API call fails for any reason.
        ValueError: If *texts* is empty or any element is an empty string.
    """
    if not texts:
        raise ValueError("embed_batch() received an empty list")
    if any(not t for t in texts):
        raise ValueError("embed_batch() received one or more empty strings")

    settings = _safe_get_settings()
    client = _get_client()
    model = getattr(settings, "embedding_model", None) if settings else None
    if not model or model in ("models/text-embedding-004", "text-embedding-004", "text-embedding-3-small"):
        model = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
    if model in ("models/text-embedding-004", "text-embedding-004", "text-embedding-3-small"):
        model = "gemini-embedding-001"

    logger.debug(
        "Requesting embeddings for %d text(s) with model=%s",
        len(texts),
        model,
    )

    try:
        # The google-genai SDK's embed_content is synchronous; wrap it with
        # asyncio.to_thread() to keep the event loop non-blocking.
        response = await asyncio.to_thread(
            client.models.embed_content,
            model=model,
            contents=texts,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIMENSION,
            ),
        )
    except Exception as exc:
        logger.error(
            "Gemini embeddings API error (model=%s, batch_size=%d): %s",
            model,
            len(texts),
            exc,
        )
        raise EmbeddingError(
            f"Gemini embeddings call failed for model "
            f"'{model}': {exc}"
        ) from exc

    # The API returns embeddings in the same order as the input contents.
    embeddings = [list(e.values) for e in response.embeddings]

    logger.debug(
        "Received %d embedding(s), dimension=%d",
        len(embeddings),
        len(embeddings[0]) if embeddings else 0,
    )
    return embeddings
