"""Stage 5 – Confidence scoring and refusal decision.

Owner: P5  |  Priority: 1
Applies the refusal rules from Section 9 of the engineering spec:
  - Priority 1: refuse if top-1 dense score < 0.72 or zero chunks survive filter.
  - Priority 2: refuse if top-1 reranked score < threshold.
  - Always: ask the LLM to self-rate confidence; low also triggers refusal.
Also calls conflict_detector.check_conflict() if that module is available.
"""

from enum import Enum
import logging
from pydantic import BaseModel, Field
import openai
from openai import AsyncOpenAI
from app.schemas import ChunkResult, RefusalDecision
from app.config import get_settings

logger = logging.getLogger(__name__)


class ConfidenceLevel(str, Enum):
    """Allowed values for LLM confidence rating."""

    high = "high"
    medium = "medium"
    low = "low"


class ConfidenceLLMResponse(BaseModel):
    """Structured output schema for the grounding confidence LLM call."""

    confidence: ConfidenceLevel = Field(
        description="How well the retrieved passages support the drafted answer."
    )
    refusal_reason: str | None = Field(
        default=None,
        description=(
            "If confidence is low, provide a user-facing refusal reason explaining why the passages "
            "do not answer the question and suggesting where to look. If confidence is high or medium, leave null."
        ),
    )


async def decide_refusal(
    query: str,
    top_chunks: list[ChunkResult],
    draft_answer: str,
) -> RefusalDecision:
    """Decide whether to refuse or surface the drafted answer.

    Args:
        query: Original (or rewritten) user query.
        top_chunks: The top-ranked chunks used to draft the answer.
        draft_answer: The LLM-generated draft answer text.

    Returns:
        RefusalDecision: refused flag, reason, confidence score, conflict flag.
    """
    settings = get_settings()
    default_refusal_reason = (
        "I couldn't find a passage in the current policy documents that directly answers this. "
        "You may want to check with [department] or rephrase your question."
    )

    # Priority 1: refuse if zero chunks survive metadata filter
    if not top_chunks:
        return RefusalDecision(
            refused=True,
            reason=default_refusal_reason,
            confidence=0.0,
            conflict=False,
        )

    # Priority 1: refuse if top-1 dense retrieval score is below threshold
    if top_chunks[0].score < settings.refusal_score_threshold:
        return RefusalDecision(
            refused=True,
            reason=default_refusal_reason,
            confidence=0.0,
            conflict=False,
        )

    # Priority 2: conflict detection (fail-safe)
    conflict = False
    try:
        from app.generation.conflict_detector import check_conflict
        conflict_res = await check_conflict(top_chunks)
        conflict = conflict_res.conflict
    except Exception as e:
        logger.warning("Failed to check conflict, falling back: %s", e)

    # Priority 1: LLM self-rate confidence
    # Retry with binary exponential backoff on transient failures.
    MAX_RETRIES = 2
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    chunk_texts = "\n\n".join([f"Chunk: {c.text}" for c in top_chunks[:5]])
    
    prompt = (
        "You are a strict evaluator. Rate your confidence that the retrieved passages support the drafted answer to the user's query.\n"
        f"Query: {query}\n\n"
        f"Retrieved passages:\n{chunk_texts}\n\n"
        f"Drafted Answer:\n{draft_answer}\n\n"
        "If confidence is 'low', provide a helpful refusal reason explaining that the passages do not contain "
        "sufficient information to answer the query directly and suggest where or what to check."
    )
    
    TRANSIENT_ERRORS = (
        openai.RateLimitError,
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.InternalServerError,
        TimeoutError,
        ConnectionError,
    )

    confidence_val = None
    llm_refusal_reason = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.responses.parse(
                model=settings.llm_model,
                input=[{"role": "user", "content": prompt}],
                text_format=ConfidenceLLMResponse,
                temperature=0.0,
            )
            result = response.output_parsed
            if result.confidence == ConfidenceLevel.high:
                confidence_val = 1.0
            elif result.confidence == ConfidenceLevel.medium:
                confidence_val = 0.5
            else:
                confidence_val = 0.0
                llm_refusal_reason = result.refusal_reason
            break
        except TRANSIENT_ERRORS as e:
            wait_seconds = 2 ** attempt  # 1s, 2s
            logger.warning(
                "Transient LLM call failed in decide_refusal (attempt %d/%d): %s. Retrying in %ds...",
                attempt + 1, MAX_RETRIES + 1, e, wait_seconds,
            )
            if attempt < MAX_RETRIES:
                import asyncio
                await asyncio.sleep(wait_seconds)
        except Exception as e:
            logger.error("Non-transient error in decide_refusal: %s. Aborting retries.", e)
            break

    # If all retries exhausted or failed, default to medium confidence rather than
    # refusing a potentially valid answer just because the API had a hiccup.
    if confidence_val is None:
        logger.error(
            "LLM evaluation did not succeed in decide_refusal. "
            "Defaulting to medium confidence.",
        )
        confidence_val = 0.5


    refused = confidence_val == 0.0
    reason = None
    if refused:
        reason = llm_refusal_reason or default_refusal_reason
    
    return RefusalDecision(
        refused=refused,
        reason=reason,
        confidence=confidence_val,
        conflict=conflict,
    )


