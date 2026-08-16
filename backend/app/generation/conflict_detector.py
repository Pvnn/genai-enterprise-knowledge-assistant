"""Stage 5, Priority 2 – Version-conflict detection.

Owner: P5  |  Priority: 2
Detects when two chunks both tagged version_status="current", from different
documents, contain contradictory information.  Called from inside
grounding.decide_refusal().
Fallback: if this module is unavailable, conflict is reported as False.
"""

import logging

from app.schemas import ChunkResult, ConflictResult

logger = logging.getLogger(__name__)


async def check_conflict(top_chunks: list[ChunkResult]) -> ConflictResult:
    """Detect conflicting information across current-version chunks.

    Args:
        top_chunks: Ranked chunks from retrieval/reranking.

    Returns:
        ConflictResult: conflict flag and, if True, the conflicting chunk pair.
    """
    raise NotImplementedError("P5: implement check_conflict() in conflict_detector.py")
