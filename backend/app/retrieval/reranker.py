"""Stage 4, Priority 2 – Cross-encoder reranking.

Owner: P3  |  Priority: 2
Uses bge-reranker-base (via FlagEmbedding / sentence-transformers) to jointly
score (query, chunk_text) pairs.  Reranks the fused top-~25 down to top-~5.
CPU-only; no GPU required.
Fallback: if this module is unavailable or raises, generator.py takes the
first top_n chunks from the retrieval result as-is.
"""

import logging

from app.schemas import ChunkResult

logger = logging.getLogger(__name__)


def rerank(query: str, chunks: list[ChunkResult], top_n: int = 5) -> list[ChunkResult]:
    """Cross-encoder rerank a list of candidate chunks.

    Args:
        query: The (possibly rewritten) user query.
        chunks: Candidate chunks from Stage 3 (dense or hybrid retrieval).
        top_n: Number of top chunks to return after reranking.

    Returns:
        list[ChunkResult]: Top-n chunks sorted by cross-encoder score (desc).
    """
    raise NotImplementedError("P3: implement rerank() in reranker.py")
