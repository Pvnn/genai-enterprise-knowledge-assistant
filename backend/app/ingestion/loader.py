"""Stage 0 (Priority 1) - Loader.

Owner: P1
"""
import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import ChunkDB
from app.retrieval.embeddings import embed_batch

logger = logging.getLogger(__name__)


async def load_chunks(session: AsyncSession, chunks: list[ChunkDB]) -> None:
    """Load chunks into the database, generating embeddings and tsvector.
    
    Args:
        session: Async SQLAlchemy session.
        chunks: List of validated ChunkDB models.
    """
    if not chunks:
        logger.warning("No chunks to load.")
        return
        
    logger.info("Loading %d chunks into the database...", len(chunks))
    
    # 1. Generate embeddings for all chunk texts
    texts = [chunk.text for chunk in chunks]
    try:
        embeddings = await embed_batch(texts)
    except NotImplementedError:
        logger.warning("embeddings.embed_batch() not implemented by P3 yet. Mocking embeddings for development.")
        # Create a mock embedding of 1536 dimensions (OpenAI text-embedding-3-small)
        embeddings = [[0.0] * 1536 for _ in texts]
    
    # 2. Bulk insert into the `chunks` table
    # We use raw SQL with SQLAlchemy text() since P2 may not have finished the Chunk ORM model yet,
    # and we need to handle pgvector and tsvector generation explicitly.
    insert_query = text("""
        INSERT INTO chunks (
            id, 
            document_id, 
            tenant_id, 
            text, 
            section_path,
            embedding, 
            text_search,
            department, 
            doc_type, 
            effective_date, 
            version_status,
            source_path
        ) VALUES (
            :id, 
            :document_id, 
            :tenant_id, 
            :text, 
            :section_path,
            :embedding,
            to_tsvector('english', :text),
            :department, 
            :doc_type, 
            :effective_date, 
            :version_status,
            :source_path
        )
    """)
    
    # Prepare parameter dictionaries for executemany
    params = []
    for chunk, emb in zip(chunks, embeddings):
        params.append({
            "id": chunk.id,
            "document_id": chunk.document_id,
            "tenant_id": chunk.tenant_id,
            "text": chunk.text,
            "section_path": chunk.section_path,
            "embedding": str(emb),  # pgvector accepts string representation of arrays e.g. '[0.1, 0.2]'
            "department": chunk.department,
            "doc_type": chunk.doc_type,
            "effective_date": chunk.effective_date,
            "version_status": chunk.version_status,
            "source_path": chunk.source_path
        })
    
    await session.execute(insert_query, params)
    
    # We do NOT commit here. The caller (run_ingestion.py) handles the transaction commit
    # so that if something fails later, the whole document ingestion rolls back.
    logger.info("Successfully loaded %d chunks.", len(chunks))
