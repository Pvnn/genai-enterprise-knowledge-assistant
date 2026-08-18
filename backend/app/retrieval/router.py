"""Retrieval router – exposes POST /retrieve.

Owner: P2
See Section 5 of the engineering spec for the exact request/response contract.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.deps import CurrentUserDep, DbDep
from app.retrieval.dense_retrieval import retrieve_chunks
from app.retrieval.embeddings import embed_text
from app.schemas import RetrieveRequest, RetrieveResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(
    request: RetrieveRequest,
    db: DbDep,
    current_user: CurrentUserDep,
) -> RetrieveResponse:
    """Retrieve relevant chunks for a query.

    Tenant isolation: the tenant_id in the request body is always overridden
    by the authenticated user's tenant_id so a user cannot query another
    tenant's data.
    """
    tenant_id = current_user.tenant_id

    try:
        query_embedding = await embed_text(request.query)
    except Exception as exc:
        logger.error("Failed to generate embedding for query: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate query embedding: {exc}",
        ) from exc

    chunks = await retrieve_chunks(
        query_embedding=query_embedding,
        tenant_id=tenant_id,
        filters=request.filters,
        top_k=request.top_k,
        session=db,
        scoped_sections=request.scoped_sections,
    )

    return RetrieveResponse(chunks=chunks)
