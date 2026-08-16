"""Stage 3, Priority 2 – BM25 + dense hybrid retrieval with RRF fusion.

Owner: P2  |  Priority: 2
Runs a BM25 full-text search on chunks.text_search (tsvector) in parallel
with dense_retrieval.retrieve_chunks(), then fuses both ranked lists using
Reciprocal Rank Fusion (RRF).
Fallback: if this module is unavailable or raises, generator.py falls back
to dense-only retrieval.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import ChunkResult, MetadataFilters, ScopedSection

logger = logging.getLogger(__name__)


async def hybrid_retrieve(
    bm25_query: str,
    query_embedding: list[float],
    tenant_id: UUID,
    filters: MetadataFilters,
    top_k: int,
    session: AsyncSession,
    scoped_sections: list[ScopedSection] | None = None,
) -> list[ChunkResult]:
    """Fuse BM25 and dense retrieval results using Reciprocal Rank Fusion.

    Args:
        bm25_query: Keyword-optimised query string for the tsvector search.
        query_embedding: Dense query vector for pgvector search.
        tenant_id: Tenant scope (hard constraint).
        filters: Hard metadata constraints.
        top_k: Number of fused results to return.
        session: Async database session.
        scoped_sections: Optional section scope from Stage 2 routing.

    Returns:
        list[ChunkResult]: RRF-fused and ranked chunks.
    """
    raise NotImplementedError("P2: implement hybrid_retrieve() in hybrid_retrieval.py")
