"""Stage 2, Priority 2 – Coarse document and section routing.

Owner: P2  |  Priority: 2
Stage 2a: metadata filter + summary-embedding match -> top 3-5 candidate docs.
Stage 2b: LLM reads each candidate document s section_tree to pick the
governing section(s).
Returns a list of (document_id, section_path) pairs used to scope Stage 3.
Fallback: if this module is unavailable, scoped_sections = None and
dense_retrieval searches the full metadata-filtered corpus.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def route_query(
    rewritten_query: str,
    tenant_id: UUID,
    session: AsyncSession,
) -> list[dict]:
    """Select the governing document(s) and section(s) for a query.

    Args:
        rewritten_query: Expanded/rewritten query from Stage 1 (or raw query).
        tenant_id: Tenant scope (hard constraint).
        session: Async database session.

    Returns:
        list[dict]: 1-3 dicts, each with keys:
            - document_id (UUID)
            - section_path (str)
    """
    raise NotImplementedError("P2: implement route_query() in routing.py")
