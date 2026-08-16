"""Stage 0, Priority 2 – Per-document LLM summary.

Owner: P1  |  Priority: 2
Generates a short summary of a document via gpt-4o-mini.  The summary is
stored in documents.summary and used by Stage 2a routing to narrow the
candidate document set.
Fallback: if this module is unavailable or raises, summary is left NULL and
Stage 2a falls back to metadata-only filtering.
"""

import logging

logger = logging.getLogger(__name__)


async def summarize_document(markdown: str) -> str:
    """Generate a concise summary of a document using gpt-4o-mini.

    Args:
        markdown: Full structured markdown of the document.

    Returns:
        str: A short (<=200 word) summary suitable for embedding-based matching.
    """
    raise NotImplementedError("P1: implement summarize_document() in summarizer.py")
