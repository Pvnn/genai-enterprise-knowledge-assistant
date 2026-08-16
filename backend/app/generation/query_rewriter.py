"""Stage 1, Priority 2 – Query rewriting.

Owner: P4  |  Priority: 2
Performs acronym expansion (from the glossary table), metadata predicate
extraction, compound-question decomposition, and produces separate BM25 /
dense phrasings.  Also decides whether a clarifying question is needed.
Depends on P1 s glossary table for acronym expansion.
Fallback: if this module is unavailable or raises, generator.py uses the raw
query as-is for both BM25 and dense, with no auto metadata filters and no
sub-query decomposition.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import RewriteResult

logger = logging.getLogger(__name__)


async def rewrite(
    raw_query: str,
    tenant_id: UUID,
    session: AsyncSession,
) -> RewriteResult:
    """Rewrite and expand a raw user query.

    Args:
        raw_query: The original query string from the user.
        tenant_id: Tenant scope (for glossary lookup).
        session: Async database session.

    Returns:
        RewriteResult: Expanded query, metadata filters, BM25/dense variants,
                       sub-queries, and optional clarifying question.
    """
    raise NotImplementedError("P4: implement rewrite() in query_rewriter.py")
