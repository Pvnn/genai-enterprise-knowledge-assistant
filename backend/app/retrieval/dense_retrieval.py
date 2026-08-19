"""Stage 3 – Dense retrieval via pgvector.

Owner: P2  |  Priority: 1
Performs ANN search over chunks.embedding using metadata filters as hard
constraints. When scoped_sections is provided (from Stage 2 routing), the
search is restricted to those (document_id, section_path) pairs.
"""

from __future__ import annotations

import json
import logging
import math
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import ChunkResult, MetadataFilters, ScopedSection

logger = logging.getLogger(__name__)


def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


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
    if top_k <= 0:
        return []

    # Detect dialect to determine if native pgvector operators are supported
    dialect_name = session.bind.dialect.name if session.bind else "postgresql"

    if dialect_name == "postgresql":
        # Try native pgvector query with cosine distance operator <=>
        try:
            return await _retrieve_pgvector(
                query_embedding=query_embedding,
                tenant_id=tenant_id,
                filters=filters,
                top_k=top_k,
                session=session,
                scoped_sections=scoped_sections,
            )
        except Exception as exc:
            logger.warning(
                "pgvector query failed, falling back to python cosine similarity: %s",
                exc,
            )
            try:
                await session.rollback()
            except Exception as rb_exc:
                logger.debug("Session rollback failed or already inactive: %s", rb_exc)

    return await _retrieve_fallback(
        query_embedding=query_embedding,
        tenant_id=tenant_id,
        filters=filters,
        top_k=top_k,
        session=session,
        scoped_sections=scoped_sections,
    )


async def _retrieve_pgvector(
    query_embedding: list[float],
    tenant_id: UUID,
    filters: MetadataFilters,
    top_k: int,
    session: AsyncSession,
    scoped_sections: list[ScopedSection] | None = None,
) -> list[ChunkResult]:
    """Execute pgvector search directly in PostgreSQL."""
    vector_str = f"[{','.join(str(x) for x in query_embedding)}]"
    params: dict = {
        "tenant_id": str(tenant_id),
        "vector_str": vector_str,
        "top_k": top_k,
    }

    where_clauses = [
        "c.tenant_id = :tenant_id",
        "c.embedding IS NOT NULL",
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
            1 - (c.embedding <=> CAST(:vector_str AS vector)) AS score
        FROM chunks c
        LEFT JOIN documents d ON c.document_id = d.id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY score DESC
        LIMIT :top_k
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


async def _retrieve_fallback(
    query_embedding: list[float],
    tenant_id: UUID,
    filters: MetadataFilters,
    top_k: int,
    session: AsyncSession,
    scoped_sections: list[ScopedSection] | None = None,
) -> list[ChunkResult]:
    """Retrieve chunks and calculate cosine similarity in Python (SQLite / fallback)."""
    params: dict = {"tenant_id": str(tenant_id)}
    where_clauses = [
        "c.tenant_id = :tenant_id",
        "c.embedding IS NOT NULL",
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
            c.embedding,
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

    scored_chunks: list[tuple[float, ChunkResult]] = []

    for row in rows:
        embedding_raw = row.embedding
        if not embedding_raw:
            continue

        if isinstance(embedding_raw, str):
            try:
                emb_list = json.loads(embedding_raw)
            except Exception:
                continue
        elif isinstance(embedding_raw, list):
            emb_list = embedding_raw
        elif hasattr(embedding_raw, "tolist"):
            emb_list = embedding_raw.tolist()
        elif hasattr(embedding_raw, "__iter__"):
            emb_list = list(embedding_raw)
        else:
            continue

        score = _cosine_similarity(query_embedding, emb_list)

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

    # Sort descending by similarity score
    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    return [chunk for _, chunk in scored_chunks[:top_k]]
