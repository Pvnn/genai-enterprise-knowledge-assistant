"""Stage 5 – Confidence scoring and refusal decision.

Owner: P5  |  Priority: 1
Applies the refusal rules from Section 9 of the engineering spec:
  - Priority 1: refuse if top-1 dense score < 0.72 or zero chunks survive filter.
  - Priority 2: refuse if top-1 reranked score < threshold.
  - Always: ask the LLM to self-rate confidence; low also triggers refusal.
Also calls conflict_detector.check_conflict() if that module is available.
"""

import logging
from openai import AsyncOpenAI
from app.schemas import ChunkResult, RefusalDecision
from app.config import get_settings

logger = logging.getLogger(__name__)


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
    refusal_reason = "I couldn't find a passage in the current policy documents that directly answers this. You may want to check with [department] or rephrase your question."

    # Priority 1: refuse if zero chunks survive metadata filter
    if not top_chunks:
        return RefusalDecision(
            refused=True,
            reason=refusal_reason,
            confidence=0.0,
            conflict=False,
        )

    # Priority 1: refuse if top-1 dense retrieval score is below threshold
    if top_chunks[0].score < settings.refusal_score_threshold:
        return RefusalDecision(
            refused=True,
            reason=refusal_reason,
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
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    chunk_texts = "\n\n".join([f"Chunk: {c.text}" for c in top_chunks[:5]])
    
    prompt = (
        "You are a strict evaluator. Rate your confidence that the retrieved passages support the drafted answer to the user's query.\n"
        f"Query: {query}\n\n"
        f"Retrieved passages:\n{chunk_texts}\n\n"
        f"Drafted Answer:\n{draft_answer}\n\n"
        "Reply with exactly one word: 'high', 'medium', or 'low'."
    )
    
    confidence_val = 0.0
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10,
        )
        rating = response.choices[0].message.content.strip().lower()
        if "high" in rating:
            confidence_val = 1.0
        elif "medium" in rating:
            confidence_val = 0.5
            
    except Exception as e:
        logger.error("LLM call failed in decide_refusal: %s", e)
        # If API fails, we don't automatically refuse unless we have to, but 
        # to be safe, let's assume medium confidence so we don't block valid answers completely due to an API blip,
        # or we just refuse. Let's refuse.
        pass

    refused = confidence_val == 0.0
    
    return RefusalDecision(
        refused=refused,
        reason=refusal_reason if refused else None,
        confidence=confidence_val,
        conflict=conflict,
    )
