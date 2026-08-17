"""Stage 0 (Priority 1) - Metadata Tagger.

Owner: P1
"""
import logging
import uuid

from app.schemas import ChunkDB

logger = logging.getLogger(__name__)


def tag_chunks(
    chunks: list[dict],
    document_id: uuid.UUID,
    tenant_id: uuid.UUID,
    department: str | None = None,
    doc_type: str | None = None,
    effective_date: str | None = None,
    version_status: str | None = "current",
    source_path: str | None = None
) -> list[ChunkDB]:
    """Enrich raw chunks with system and document metadata.
    
    Args:
        chunks: List of raw dictionaries containing 'text' and 'section_path'.
        document_id: The UUID of the parent document.
        tenant_id: The UUID of the tenant this document belongs to.
        department: The department category of the document.
        doc_type: The type category of the document (e.g., policy, syllabus).
        effective_date: The date this document becomes or became effective.
        version_status: The version status (e.g., 'current', 'archived').
        source_path: Optional path or URI of the original source document.
        
    Returns:
        A list of validated ChunkDB Pydantic models.
    """
    logger.info("Tagging %d chunks for document %s (tenant: %s)", len(chunks), document_id, tenant_id)
    
    tagged_chunks: list[ChunkDB] = []
    
    for chunk in chunks:
        # Ensure we generate a fresh UUID for every chunk row in the DB
        chunk_id = uuid.uuid4()
        
        # Instantiate the validated Pydantic model
        chunk_db = ChunkDB(
            id=chunk_id,
            document_id=document_id,
            tenant_id=tenant_id,
            text=chunk.get("text", ""),
            section_path=chunk.get("section_path", "Document Start"),
            department=department,
            doc_type=doc_type,
            effective_date=effective_date,
            version_status=version_status,
            source_path=source_path
        )
        
        tagged_chunks.append(chunk_db)
        
    logger.debug("Successfully tagged %d chunks", len(tagged_chunks))
    return tagged_chunks
