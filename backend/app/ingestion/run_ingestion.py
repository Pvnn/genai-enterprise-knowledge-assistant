"""Stage 0 (Priority 1) - Ingestion Pipeline Orchestrator.

Owner: P1
"""
import logging
from uuid import UUID

from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal

from app.models import Document, IngestionStatus
from app.ingestion.ocr import parse_document
from app.ingestion.chunker import chunk_document
from app.ingestion.metadata_tagger import tag_chunks
from app.ingestion.loader import load_chunks

logger = logging.getLogger(__name__)


async def ingest_document(
    file_path: str,
    document_id: UUID,
    tenant_id: UUID,
    department: str | None,
    doc_type: str | None,
) -> None:
    """Orchestrate the end-to-end ingestion pipeline for a single document.
    
    Args:
        file_path: Absolute path to the saved PDF file.
        document_id: The UUID of the document row created by the API.
        tenant_id: The UUID of the tenant.
        department: The department assigned to this document.
        doc_type: The document type assigned.
    """
    logger.info("Starting ingestion pipeline for document %s", document_id)
    
    async with AsyncSessionLocal() as session:
        try:
            # 1. Fetch the Document to get its metadata and update status
            result = await session.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = result.scalars().first()
            if not doc:
                raise ValueError(f"Document {document_id} not found in database")
                
            # Default version_status to 'current' if not set
            if not doc.version_status:
                doc.version_status = "current"
                
            doc_effective_date = doc.effective_date
            doc_version_status = doc.version_status
            
            doc.ingestion_status = IngestionStatus.PROCESSING.value
            await session.commit()
            
            # 2. Stage 0.1 - OCR Parsing
            logger.info("Parsing document with Docling (OCR)...")
            # In a real environment, we'd read OCR_DEVICE from config. We let the default handle it here.
            markdown_text = parse_document(file_path)
            
            # 3. Stage 0.2 - Chunking
            logger.info("Chunking markdown output...")
            raw_chunks = chunk_document(markdown_text)
            
            # 4. Stage 0.3 - Metadata Tagging
            logger.info("Tagging chunks with document metadata...")
            tagged_chunks = tag_chunks(
                chunks=raw_chunks,
                document_id=document_id,
                tenant_id=tenant_id,
                department=department,
                doc_type=doc_type,
                effective_date=doc_effective_date,
                version_status=doc_version_status,
                source_path=file_path
            )
            
            # 5. Stage 0.4 - Loading (Embeddings & Database Insert)
            logger.info("Loading chunks into database...")
            await load_chunks(session, tagged_chunks)
            
            # 6. Mark as DONE
            await session.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(ingestion_status=IngestionStatus.DONE.value)
            )
            await session.commit()
            logger.info("Successfully ingested document %s", document_id)
            
        except Exception as e:
            logger.error("Ingestion failed for document %s: %s", document_id, str(e), exc_info=True)
            # Attempt to roll back any pending chunk inserts
            await session.rollback()
            
            # Mark as FAILED
            try:
                await session.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(ingestion_status=IngestionStatus.FAILED.value)
                )
                await session.commit()
            except Exception as fallback_err:
                logger.error("Failed to update document status to FAILED: %s", fallback_err)
