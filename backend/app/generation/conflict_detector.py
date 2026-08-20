"""Stage 5, Priority 2 – Version-conflict detection.

Owner: P5  |  Priority: 2
Detects when two chunks both tagged version_status="current", from different
documents, contain contradictory information.  Called from inside
grounding.decide_refusal().
Fallback: if this module is unavailable, conflict is reported as False.
"""

import logging
from pydantic import BaseModel, Field
import openai
from openai import AsyncOpenAI
from app.schemas import ChunkResult, ConflictResult
from app.config import get_settings

logger = logging.getLogger(__name__)


class ConflictLLMResponse(BaseModel):
    """Internal structured output schema for the conflict-detection LLM call."""

    has_contradiction: bool = Field(
        description="True if the excerpts directly contradict each other, False otherwise."
    )


async def check_conflict(top_chunks: list[ChunkResult]) -> ConflictResult:
    """Detect conflicting information across current-version chunks.

    Args:
        top_chunks: Ranked chunks from retrieval/reranking.

    Returns:
        ConflictResult: conflict flag and, if True, the conflicting chunk pair.
    """
    settings = get_settings()

    current_chunks = [c for c in top_chunks if c.version_status == "current"]
    
    if len(current_chunks) < 2:
        return ConflictResult(conflict=False)
        
    doc_ids = {c.document_id for c in current_chunks}
    if len(doc_ids) < 2:
        return ConflictResult(conflict=False)
        
    chunk_texts = ""
    for i, chunk in enumerate(current_chunks):
        chunk_texts += f"Chunk {i+1} (Doc {chunk.document_id}):\n{chunk.text}\n\n"
        
    prompt = (
        "You are an expert policy analyst. Review the following excerpts from current policy documents.\n"
        "Determine if any of these excerpts directly contradict each other regarding the same topic.\n"
        "Respond in JSON format with a single key 'has_contradiction' mapping to a boolean.\n\n"
        f"{chunk_texts}"
    )
    
    TRANSIENT_ERRORS = (
        openai.RateLimitError,
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.InternalServerError,
        TimeoutError,
        ConnectionError,
    )

    # Retry with binary exponential backoff on transient failures.
    MAX_RETRIES = 2
    from app.llm import get_llm_client, get_llm_model
    import json

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        if type(client).__name__ == "AsyncOpenAI" and settings.openai_api_key and settings.openai_api_key.startswith("gsk_"):
            client = get_llm_client()
    except Exception:
        client = get_llm_client()

    model = get_llm_model()
    result = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            if hasattr(client, "responses") and hasattr(client.responses, "parse"):
                response = await client.responses.parse(
                    model=model,
                    input=[{"role": "user", "content": prompt}],
                    text_format=ConflictLLMResponse,
                    temperature=0.0,
                )
                result = response.output_parsed
            else:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
                data = json.loads(response.choices[0].message.content)
                result = ConflictLLMResponse(has_contradiction=bool(data.get("has_contradiction", False)))
            break
        except TRANSIENT_ERRORS as e:
            wait_seconds = 2 ** attempt  # 1s, 2s
            logger.warning(
                "Transient LLM call failed in check_conflict (attempt %d/%d): %s. Retrying in %ds...",
                attempt + 1, MAX_RETRIES + 1, e, wait_seconds,
            )
            if attempt < MAX_RETRIES:
                import asyncio
                await asyncio.sleep(wait_seconds)
        except Exception as e:
            logger.error("Non-transient error in check_conflict: %s. Aborting retries.", e)
            break

    if result is not None and result.has_contradiction:
        conflict_pair = [current_chunks[0]]
        for c in current_chunks[1:]:
            if c.document_id != conflict_pair[0].document_id:
                conflict_pair.append(c)
                break
        return ConflictResult(conflict=True, conflicting_chunks=conflict_pair)

    return ConflictResult(conflict=False)


