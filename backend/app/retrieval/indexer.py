"""Stage 0 – Batch embedding and pgvector storage.

Owner: P3  |  Priority: 1
Reads un-embedded chunks from the DB, calls embed_batch(), and writes the
vectors back to chunks.embedding.  Designed to run as an offline job after
loader.py has populated the chunks table.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def index_chunks(session: AsyncSession, tenant_id: str) -> int:
    """Embed all unindexed chunks for a tenant and write vectors to the DB.

    Args:
        session: Async database session.
        tenant_id: Tenant whose chunks should be indexed.

    Returns:
        int: Number of chunks indexed.
    """
    raise NotImplementedError("P3: implement index_chunks() in indexer.py")
