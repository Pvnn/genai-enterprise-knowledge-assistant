"""Stage 3, Priority 2 – BM25 + dense hybrid retrieval with RRF fusion.

Owner: P2  |  Priority: 2
Runs a BM25 full-text search on chunks.text_search (tsvector) in parallel
with dense_retrieval.retrieve_chunks(), then fuses both ranked lists using
Reciprocal Rank Fusion (RRF).
Fallback: if this module is unavailable or raises, generator.py falls back
to dense-only retrieval.
"""

from __future__ import annotations

import asyncio
import logging
import re
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.dense_retrieval import retrieve_chunks
from app.schemas import ChunkResult, MetadataFilters, ScopedSection

logger = logging.getLogger(__name__)

# Standard RRF smoothing constant
RRF_K: int = 60


async def _search_bm25(
    bm25_query: str,
    tenant_id: UUID,
    filters: MetadataFilters,
    limit: int,
    session: AsyncSession,
    scoped_sections: list[ScopedSection] | None = None,
) -> list[ChunkResult]:
    """Perform BM25 / keyword search against chunks."""
    if not bm25_query.strip():
        return []

    dialect_name = session.bind.dialect.name if session.bind else "postgresql"

    if dialect_name == "postgresql":
        try:
            return await _search_bm25_postgres(
                bm25_query=bm25_query,
                tenant_id=tenant_id,
                filters=filters,
                limit=limit,
                session=session,
                scoped_sections=scoped_sections,
            )
        except Exception as exc:
            logger.warning("Postgres tsvector search failed, falling back: %s", exc)

    return await _search_bm25_fallback(
        bm25_query=bm25_query,
        tenant_id=tenant_id,
        filters=filters,
        limit=limit,
        session=session,
        scoped_sections=scoped_sections,
    )


async def _search_bm25_postgres(
    bm25_query: str,
    tenant_id: UUID,
    filters: MetadataFilters,
    limit: int,
    session: AsyncSession,
    scoped_sections: list[ScopedSection] | None = None,
) -> list[ChunkResult]:
    """Execute Postgres tsvector full-text search."""
    params: dict = {
        "tenant_id": str(tenant_id),
        "bm25_query": bm25_query,
        "limit": limit,
    }

    where_clauses = [
        "c.tenant_id = :tenant_id",
        "(to_tsvector('english', c.text) @@ plainto_tsquery('english', :bm25_query))",
    ]

    if filters.department:
        where_clauses.append("c.department = :department")
        params["department"] = filters.department
    if filters.doc_type:
        where_clauses.append("c.doc_type = :doc_type")
        params["doc_type"] = filters.doc_type
    if filters.version_status:
        where_clauses.append("c.version_status = :version_status")
        params["version_status"] = filters.version_status

    if scoped_sections:
        scoped_conditions = []
        for i, s in enumerate(scoped_sections):
            doc_param = f"doc_{i}"
            sec_param = f"sec_{i}"
            params[doc_param] = str(s.document_id)
            params[sec_param] = f"{s.section_path}%"
            scoped_conditions.append(
                f"(c.document_id = :{doc_param} AND (c.section_path = :{sec_param} OR c.section_path LIKE :{sec_param}))"
            )
        where_clauses.append(f"({' OR '.join(scoped_conditions)})")

    query_sql = f"""
        SELECT 
            c.id AS chunk_id,
            c.document_id,
            c.text,
            c.section_path,
            c.department,
            c.doc_type,
            c.effective_date,
            c.version_status,
            d.source_path,
            ts_rank(to_tsvector('english', c.text), plainto_tsquery('english', :bm25_query)) AS score
        FROM chunks c
        LEFT JOIN documents d ON c.document_id = d.id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY score DESC
        LIMIT :limit
    """

    result = await session.execute(text(query_sql), params)
    rows = result.fetchall()

    return [
        ChunkResult(
            chunk_id=UUID(str(row.chunk_id)),
            document_id=UUID(str(row.document_id)),
            text=row.text,
            section_path=row.section_path,
            score=float(row.score) if row.score is not None else 0.0,
            department=row.department,
            doc_type=row.doc_type,
            effective_date=row.effective_date,
            version_status=row.version_status,
            source_path=row.source_path,
        )
        for row in rows
    ]


async def _search_bm25_fallback(
    bm25_query: str,
    tenant_id: UUID,
    filters: MetadataFilters,
    limit: int,
    session: AsyncSession,
    scoped_sections: list[ScopedSection] | None = None,
) -> list[ChunkResult]:
    """Execute keyword matching fallback for SQLite or when tsvector is unavailable."""
    params: dict = {"tenant_id": str(tenant_id)}
    where_clauses = ["c.tenant_id = :tenant_id"]

    if filters.department:
        where_clauses.append("c.department = :department")
        params["department"] = filters.department
    if filters.doc_type:
        where_clauses.append("c.doc_type = :doc_type")
        params["doc_type"] = filters.doc_type
    if filters.version_status:
        where_clauses.append("c.version_status = :version_status")
        params["version_status"] = filters.version_status

    if scoped_sections:
        scoped_conditions = []
        for i, s in enumerate(scoped_sections):
            doc_param = f"doc_{i}"
            sec_param = f"sec_{i}"
            sec_param_prefix = f"sec_prefix_{i}"
            params[doc_param] = str(s.document_id)
            params[sec_param] = str(s.section_path)
            params[sec_param_prefix] = f"{s.section_path}%"
            scoped_conditions.append(
                f"(c.document_id = :{doc_param} AND (c.section_path = :{sec_param} OR c.section_path LIKE :{sec_param_prefix}))"
            )
        where_clauses.append(f"({' OR '.join(scoped_conditions)})")

    query_sql = f"""
        SELECT 
            c.id AS chunk_id,
            c.document_id,
            c.text,
            c.section_path,
            c.department,
            c.doc_type,
            c.effective_date,
            c.version_status,
            d.source_path
        FROM chunks c
        LEFT JOIN documents d ON c.document_id = d.id
        WHERE {' AND '.join(where_clauses)}
    """

    result = await session.execute(text(query_sql), params)
    rows = result.fetchall()

    keywords = [w.lower() for w in re.findall(r"\w+", bm25_query) if len(w) > 2]
    if not keywords:
        return []

    scored_chunks: list[tuple[float, ChunkResult]] = []

    for row in rows:
        text_lower = row.text.lower()
        # Compute term frequency score
        match_count = sum(text_lower.count(k) for k in keywords)
        if match_count == 0:
            continue

        score = float(match_count) / (1.0 + len(text_lower.split()))
        chunk_res = ChunkResult(
            chunk_id=UUID(str(row.chunk_id)),
            document_id=UUID(str(row.document_id)),
            text=row.text,
            section_path=row.section_path,
            score=round(score, 6),
            department=row.department,
            doc_type=row.doc_type,
            effective_date=row.effective_date,
            version_status=row.version_status,
            source_path=row.source_path,
        )
        scored_chunks.append((score, chunk_res))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored_chunks[:limit]]


async def hybrid_retrieve(
    bm25_query: str,
    query_embedding: list[float],
    tenant_id: UUID,
    filters: MetadataFilters,
    top_k: int,
    session: AsyncSession,
    scoped_sections: list[ScopedSection] | None = None,
) -> list[ChunkResult]:
    """Fuse BM25 and dense retrieval results using Reciprocal Rank Fusion (RRF).

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
    fetch_limit = max(top_k * 2, 50)

    # Run dense retrieval and BM25 search in parallel
    dense_task = retrieve_chunks(
        query_embedding=query_embedding,
        tenant_id=tenant_id,
        filters=filters,
        top_k=fetch_limit,
        session=session,
        scoped_sections=scoped_sections,
    )
    bm25_task = _search_bm25(
        bm25_query=bm25_query,
        tenant_id=tenant_id,
        filters=filters,
        limit=fetch_limit,
        session=session,
        scoped_sections=scoped_sections,
    )

    dense_results, bm25_results = await asyncio.gather(dense_task, bm25_task)

    # If one of the lists is empty, return the other directly
    if not bm25_results:
        return dense_results[:top_k]
    if not dense_results:
        return bm25_results[:top_k]

    # Reciprocal Rank Fusion
    rrf_scores: dict[UUID, float] = {}
    chunk_map: dict[UUID, ChunkResult] = {}

    for rank, chunk in enumerate(dense_results, start=1):
        rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + (1.0 / (RRF_K + rank))
        chunk_map[chunk.chunk_id] = chunk

    for rank, chunk in enumerate(bm25_results, start=1):
        rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + (1.0 / (RRF_K + rank))
        if chunk.chunk_id not in chunk_map:
            chunk_map[chunk.chunk_id] = chunk

    # Sort chunks by fused RRF score descending
    sorted_items = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)

    fused_chunks: list[ChunkResult] = []
    for chunk_id, fused_score in sorted_items[:top_k]:
        base_chunk = chunk_map[chunk_id]
        fused_chunks.append(
            ChunkResult(
                chunk_id=base_chunk.chunk_id,
                document_id=base_chunk.document_id,
                text=base_chunk.text,
                section_path=base_chunk.section_path,
                score=round(fused_score, 6),
                department=base_chunk.department,
                doc_type=base_chunk.doc_type,
                effective_date=base_chunk.effective_date,
                version_status=base_chunk.version_status,
                source_path=base_chunk.source_path,
            )
        )

    return fused_chunks
