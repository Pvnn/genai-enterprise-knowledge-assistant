"""Stage 0, Priority 2 – Per-document LLM summary.

Owner: P1  |  Priority: 2
Generates a short summary of a document via gpt-4o-mini.  The summary is
stored in documents.summary and used by Stage 2a routing to narrow the
candidate document set.
Fallback: if this module is unavailable or raises, summary is left NULL and
Stage 2a falls back to metadata-only filtering.
"""

import logging
from openai import AsyncOpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
# Rely on environment variables (like OPENAI_BASE_URL) for OpenAI-compatible endpoints
_client = AsyncOpenAI(api_key=settings.openai_api_key)

async def summarize_document(markdown: str) -> str:
    """Generate a concise summary of a document using gpt-4o-mini (or configured LLM).

    Args:
        markdown: Full structured markdown of the document.

    Returns:
        str: A short (<=200 word) summary suitable for embedding-based matching.
    """
    if not settings.openai_api_key:
        logger.warning("No OpenAI API key provided. Skipping summarization.")
        raise ValueError("Missing OpenAI API key")

    messages = [
        {
            "role": "system",
            "content": "You are a precise technical summarizer. Extract the core purpose and key rules of the provided document in 200 words or less. Do not include introductory fluff.",
        },
        {"role": "user", "content": markdown[:100000]}, # Truncate to avoid context limits if extremely large
    ]

    response = await _client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        max_tokens=300,
        temperature=0.3,
    )
    
    summary = response.choices[0].message.content
    return summary.strip() if summary else ""
