"""Stage 3 – Dense retrieval via pgvector.

Owner: P2  |  Priority: 1
Performs ANN search over chunks.embedding using metadata filters as hard
constraints.  When scoped_sections is provided (from Stage 2 routing), the
search is restricted to those (document_id, section_path) pairs.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import ChunkResult, MetadataFilters, ScopedSection

logger = logging.getLogger(__name__)


async def retrieve_chunks(
    query_embedding: list[float],
    tenant_id: UUID,
    filters: MetadataFilters,
    top_k: int,
    session: AsyncSession,
    scoped_sections: list[ScopedSection] | None = None,
) -> list[ChunkResult]:
    """Retrieve the top-k most relevant chunks via pgvector ANN search.

    Args:
        query_embedding: The dense query vector from embeddings.embed_text().
        tenant_id: Tenant scope (hard constraint; never omit).
        filters: Hard metadata constraints (department, doc_type, version_status).
        top_k: Maximum number of chunks to return.
        session: Async database session.
        scoped_sections: If provided, restrict search to these doc/section pairs
                         (Stage 2 output; None means search full corpus).

    Returns:
        list[ChunkResult]: Ranked chunks sorted by descending similarity score.
    """
    raise NotImplementedError("P2: implement retrieve_chunks() in dense_retrieval.py")
