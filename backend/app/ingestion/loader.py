"""Stage 0 – Database writer.

Owner: P1  |  Priority: 1
Writes documents, chunks, and all metadata produced by the ingestion pipeline
into the database.  Depends on P2 s database session and schemas.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def load_document(
    session: AsyncSession,
    tenant_id: str,
    source_path: str,
    metadata: dict,
    chunks: list[dict],
) -> str:
    """Persist a document and its chunks to the database.

    Args:
        session: Open AsyncSession from P2 s database.py.
        tenant_id: The tenant this document belongs to.
        source_path: Original path of the PDF.
        metadata: Dict from metadata_tagger.tag_metadata().
        chunks: List of chunk dicts from chunker.chunk_document().

    Returns:
        str: The UUID of the newly created document record.
    """
    raise NotImplementedError("P1: implement load_document() in loader.py")
