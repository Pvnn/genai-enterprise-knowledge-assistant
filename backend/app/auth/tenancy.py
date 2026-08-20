"""Tenant isolation helpers.

Owner: P6
Utility functions to resolve a tenant_code (from the login request) to a
tenant_id UUID, and to assert tenant isolation on DB queries.
"""

import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Enterprise

logger = logging.getLogger(__name__)


async def resolve_tenant(tenant_code: str, session: AsyncSession) -> UUID:
    """Look up a tenant UUID by its human-readable tenant code.

    Matches against Enterprise.name case-insensitively. The tenant_code
    field in the login request should be the enterprise name as registered
    in the enterprises table (e.g. "Acme University").

    Args:
        tenant_code: The tenant identifier provided in the login request,
                     matched case-insensitively against enterprises.name.
        session: Async database session.

    Returns:
        UUID: The tenant_id for use in all subsequent queries.

    Raises:
        HTTPException: 400 if no enterprise with that name exists.
    """
    result = await session.execute(
        select(Enterprise).where(Enterprise.name.ilike(tenant_code))
    )
    enterprise: Enterprise | None = result.scalar_one_or_none()

    if enterprise is None:
        logger.warning("Login attempt with unknown tenant_code=%r", tenant_code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown organisation: {tenant_code!r}",
        )

    logger.info(
        "Resolved tenant_code=%r to tenant_id=%s", tenant_code, enterprise.id
    )
    return enterprise.id
