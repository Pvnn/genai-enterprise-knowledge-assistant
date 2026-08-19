"""Stage 0, Priority 2 - Per-document LLM summary.

Owner: P1  |  Priority: 2
Generates a short summary of a document via structured output.  The summary is
stored in documents.summary and used by Stage 2a routing to narrow the
candidate document set.
"""

import logging
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

client_kwargs = {"api_key": settings.openai_api_key}
if settings.openai_api_key and settings.openai_api_key.startswith("gsk_"):
    client_kwargs["base_url"] = "https://api.groq.com/openai/v1"

_client = AsyncOpenAI(**client_kwargs)

class SummaryResponse(BaseModel):
    summary: str = Field(description="A concise summary of the document, up to 200 words. Extract the core purpose and key rules of the provided document. Do not include introductory fluff.")

async def summarize_document(markdown: str) -> str:
    """Generate a concise summary of a document.

    Args:
        markdown: Full structured markdown of the document.

    Returns:
        str: A short (<=200 word) summary suitable for embedding-based matching.
    """
    if not settings.openai_api_key:
        logger.warning("No OpenAI API key provided. Skipping summarization.")
        raise ValueError("Missing OpenAI API key")

    prompt = f"Summarize the following document:\n\n{markdown[:100000]}"

    response = await _client.responses.parse(
        model=settings.llm_model,
        input=[{"role": "user", "content": prompt}],
        text_format=SummaryResponse,
        temperature=0.0,
    )
    
    result = response.output_parsed
    return result.summary.strip()
