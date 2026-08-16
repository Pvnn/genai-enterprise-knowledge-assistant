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
from app.schemas import DocumentStatusResponse, UploadResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["ingestion"])


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
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
    BackgroundTask.  The endpoint returns immediately with ingestion_status
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

    # P1: replace the stub below with real DB row creation and background dispatch
    raise NotImplementedError(
        "P1: implement upload_document() in ingestion/router.py — "
        "save file to temp path, create documents row with ingestion_status='pending', "
        "then call background_tasks.add_task(ingest_document, file_path, tenant_id, "
        "department, doc_type)."
    )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
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
    # P1: replace the stub below with a real DB lookup scoped to current_user.tenant_id
    raise NotImplementedError(
        "P1: implement get_document_status() in ingestion/router.py — "
        "query documents table for id=document_id AND tenant_id=current_user.tenant_id, "
        "return 404 if not found, else return DocumentStatusResponse."
    )