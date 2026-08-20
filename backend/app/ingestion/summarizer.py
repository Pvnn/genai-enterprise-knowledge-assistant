"""Stage 0, Priority 2 - Per-document LLM summary.

Owner: P1  |  Priority: 2
Generates a short summary of a document via structured output.  The summary is
stored in documents.summary and used by Stage 2a routing to narrow the
candidate document set.
"""

import logging
import json
import logging
from app.config import get_settings
from app.llm import get_llm_client, get_llm_model

logger = logging.getLogger(__name__)


async def summarize_document(markdown: str) -> str:
    """Generate a concise summary of a document.

    Args:
        markdown: Full structured markdown of the document.

    Returns:
        str: A short (<=200 word) summary suitable for embedding-based matching.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("No OpenAI API key provided. Skipping summarization.")
        raise ValueError("Missing OpenAI API key")

    client = get_llm_client()
    model = get_llm_model()

    prompt = (
        "Summarize the following document in up to 200 words. "
        "Extract the core purpose and key rules of the provided document. "
        "Return a JSON object with key 'summary'.\n\n"
        f"{markdown[:100000]}"
    )

    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    data = json.loads(response.choices[0].message.content)
    return str(data.get("summary", "")).strip()
