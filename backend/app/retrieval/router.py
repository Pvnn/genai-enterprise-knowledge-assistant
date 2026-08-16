"""Retrieval router – exposes POST /retrieve.

Owner: P2
See Section 5 of the engineering spec for the exact request/response contract.
"""

import logging

from fastapi import APIRouter, Depends

from app.deps import CurrentUserDep, DbDep
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
    by the authenticated user s tenant_id so a user cannot query another
    tenant s data.
    """
    raise NotImplementedError("P2: implement /retrieve endpoint in retrieval/router.py")
