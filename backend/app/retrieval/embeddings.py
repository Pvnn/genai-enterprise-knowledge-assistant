"""Embeddings API wrapper.

Owner: P3  |  Priority: 1
Wraps the OpenAI text-embedding-3-small API.  Used by the indexer (Stage 0)
and dense retrieval (Stage 3).
"""

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def embed_text(text: str) -> list[float]:
    """Embed a single text string.

    Args:
        text: The text to embed.

    Returns:
        list[float]: The embedding vector.
    """
    raise NotImplementedError("P3: implement embed_text() in embeddings.py")


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of text strings in a single API call.

    Args:
        texts: List of strings to embed.

    Returns:
        list[list[float]]: One embedding vector per input string, in order.
    """
    raise NotImplementedError("P3: implement embed_batch() in embeddings.py")
