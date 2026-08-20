"""Ingestion router – POST /documents/upload and GET /documents/{document_id}/status.

Owner: P1
Exposes the two endpoints added in the spec addendum (Section 5).

POST /documents/upload
  - Admin-only (current_user.role == "admin"), enforced via the existing
    get_current_user dependency from app.deps — no new auth logic added.
  - Accepts a PDF file upload + department + doc_type form fields.
  - Writes the file to a temp location, creates a documents row with
    ingestion_status="pending", then hands off to ingest_document() via
    FastAPI BackgroundTasks (not inline — request returns immediately).

GET /documents/{document_id}/status
  - Any authenticated user within the same tenant may poll this.
  - Returns { document_id, ingestion_status, detail }.
"""

import logging
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from fastapi import File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentUserDep, DbDep
from app.ingestion.run_ingestion import ingest_document
from app.schemas import DocumentStatusResponse, UploadResponse, DocumentItem

logger = logging.getLogger(__name__)

router = APIRouter()

documents_router = APIRouter(prefix="/documents", tags=["ingestion"])
glossary_router = APIRouter(prefix="/glossary", tags=["glossary"])

@documents_router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(..., description="PDF file to ingest"),
    department: str = Form(..., description="Department tag, e.g. HR"),
    doc_type: str = Form(..., description="Document type tag, e.g. policy"),
) -> UploadResponse:
    """Upload a PDF and trigger async ingestion (admin only).

    The file is saved to a temporary path and ingestion is dispatched as a
    BackgroundTask. The endpoint returns immediately with ingestion_status
    "pending"; poll GET /documents/{document_id}/status for progress.

    Args:
        background_tasks: FastAPI background task queue.
        db: Async database session.
        current_user: Authenticated user from JWT (provided by get_current_user).
        file: The uploaded PDF file.
        department: Department metadata tag.
        doc_type: Document type metadata tag.

    Returns:
        UploadResponse: { document_id, ingestion_status: "pending" }

    Raises:
        HTTPException 403: If the authenticated user is not an admin.
        HTTPException 400: If the uploaded file is not a PDF.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users may upload documents.",
        )

    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted.",
        )

    import uuid
    import shutil
    from app.models import Document, IngestionStatus

    temp_dir = Path(tempfile.gettempdir())
    document_id = uuid.uuid4()
    
    file_path = temp_dir / f"{document_id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    doc = Document(
        id=document_id,
        tenant_id=current_user.tenant_id,
        title=file.filename,
        department=department,
        doc_type=doc_type,
        ingestion_status=IngestionStatus.PENDING.value
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    
    background_tasks.add_task(
        ingest_document,
        file_path=str(file_path),
        document_id=document_id,
        tenant_id=current_user.tenant_id,
        department=department,
        doc_type=doc_type
    )
    
    return UploadResponse(
        document_id=document_id,
        ingestion_status=IngestionStatus.PENDING.value
    )


@documents_router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> DocumentStatusResponse:
    """Poll the ingestion status of a previously uploaded document.

    Args:
        document_id: UUID of the document to check.
        db: Async database session.
        current_user: Authenticated user (tenant isolation enforced).

    Returns:
        DocumentStatusResponse: { document_id, ingestion_status, detail }

    Raises:
        HTTPException 404: If no document with that ID exists for the tenant.
    """
    from sqlalchemy import select
    from app.models import Document
    
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == current_user.tenant_id
        )
    )
    doc = result.scalars().first()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )
        
    return DocumentStatusResponse(
        document_id=doc.id,
        ingestion_status=doc.ingestion_status,
        detail=None
    )


@documents_router.get("/{document_id}/content")
async def get_document_content(
    document_id: UUID,
    db: DbDep,
    current_user: CurrentUserDep,
):
    """Retrieve the full markdown text of a document from Neon Object Storage.

    Args:
        document_id: UUID of the document to fetch.
        db: Async database session.
        current_user: Authenticated user (tenant isolation enforced).

    Returns:
        PlainTextResponse: The plaintext markdown content of the document.

    Raises:
        HTTPException 404: If the document does not exist or has no stored content.
        HTTPException 500: If there is an error retrieving from Neon storage.
    """
    from sqlalchemy import select
    from fastapi.responses import PlainTextResponse
    from app.models import Document
    from app.ingestion.storage import get_markdown
    
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == current_user.tenant_id
        )
    )
    doc = result.scalars().first()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )
        
    if not doc.source_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document content not available in storage."
        )
        
    try:
        content = await get_markdown(doc.source_path)
        if content is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Storage credentials not configured."
            )
        return PlainTextResponse(content=content)
    except Exception as e:
        logger.error("Failed to retrieve document %s content: %s", document_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document content from storage."
        )


@documents_router.get("", response_model=list[DocumentItem])
async def list_documents(
    db: DbDep,
    current_user: CurrentUserDep,
    tenant_id: UUID | None = None,
) -> list[DocumentItem]:
    """List all documents for the current tenant.
    
    The tenant_id query param is accepted for frontend compatibility but is
    ignored in favor of current_user.tenant_id to ensure tenant isolation.
    """
    from sqlalchemy import select
    from app.models import Document
    
    result = await db.execute(
        select(Document).where(Document.tenant_id == current_user.tenant_id).order_by(Document.title)
    )
    docs = result.scalars().all()
    
    return [
        DocumentItem(
            id=doc.id,
            tenant_id=doc.tenant_id,
            title=doc.title,
            department=doc.department,
            doc_type=doc.doc_type,
            effective_date=doc.effective_date,
            version_status=doc.version_status,
            source_path=doc.source_path,
            summary=doc.summary,
            chunk_count=None,
            ingestion_status=doc.ingestion_status
        )
        for doc in docs
    ]


@glossary_router.get("")
async def get_glossary(
    db: DbDep,
    current_user: CurrentUserDep,
):
    """Get the enterprise-level glossary for the current tenant.

    Args:
        db: Async database session.
        current_user: Authenticated user (tenant isolation enforced).

    Returns:
        dict: A dictionary containing a list of glossary entries.
    """
    from sqlalchemy import text
    
    res = await db.execute(
        text("SELECT term, expansion FROM glossary WHERE tenant_id = :tenant_id ORDER BY term ASC"),
        {"tenant_id": current_user.tenant_id}
    )
    
    entries = [{"term": row.term, "expansion": row.expansion} for row in res.fetchall()]
    return {"entries": entries}

router.include_router(documents_router)
router.include_router(glossary_router)