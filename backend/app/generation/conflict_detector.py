"""Stage 5, Priority 2 – Version-conflict detection.

Owner: P5  |  Priority: 2
Detects when two chunks both tagged version_status="current", from different
documents, contain contradictory information.  Called from inside
grounding.decide_refusal().
Fallback: if this module is unavailable, conflict is reported as False.
"""

import logging
from openai import AsyncOpenAI
from app.schemas import ChunkResult, ConflictResult
from app.config import get_settings

logger = logging.getLogger(__name__)


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
        "Reply with exactly one word: 'YES' if there is a contradiction, or 'NO' if there is no contradiction.\n\n"
        f"{chunk_texts}"
    )
    
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10,
        )
        answer = response.choices[0].message.content.strip().lower()
        
        if "yes" in answer:
            conflict_pair = [current_chunks[0]]
            for c in current_chunks[1:]:
                if c.document_id != conflict_pair[0].document_id:
                    conflict_pair.append(c)
                    break
            return ConflictResult(conflict=True, conflicting_chunks=conflict_pair)
            
    except Exception as e:
        logger.error("LLM call failed in check_conflict: %s", e)
        return ConflictResult(conflict=False)

    return ConflictResult(conflict=False)
