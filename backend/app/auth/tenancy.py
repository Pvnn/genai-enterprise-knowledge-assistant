"""Tenant isolation helpers.

Owner: P6
Utility functions to resolve a tenant_code (from the login request) to a
tenant_id UUID, and to assert tenant isolation on DB queries.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def resolve_tenant(tenant_code: str, session: AsyncSession) -> UUID:
    """Look up a tenant UUID by its human-readable tenant code.

    Args:
        tenant_code: The tenant identifier provided in the login request.
        session: Async database session.

    Returns:
        UUID: The tenant_id for use in all subsequent queries.

    Raises:
        ValueError: If no enterprise with that code exists.
    """
    raise NotImplementedError("P6: implement resolve_tenant() in tenancy.py")
