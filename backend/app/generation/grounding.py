"""Stage 5 – Confidence scoring and refusal decision.

Owner: P5  |  Priority: 1
Applies the refusal rules from Section 9 of the engineering spec:
  - Priority 1: refuse if top-1 dense score < 0.72 or zero chunks survive filter.
  - Priority 2: refuse if top-1 reranked score < threshold.
  - Always: ask the LLM to self-rate confidence; low also triggers refusal.
Also calls conflict_detector.check_conflict() if that module is available.
"""

import logging

from app.schemas import ChunkResult, RefusalDecision

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
    raise NotImplementedError("P5: implement decide_refusal() in grounding.py")
