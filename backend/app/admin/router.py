"""Admin router for enterprise analytics, document management, user management, and glossary controls.

Owner: Enterprise Administration
Enforces strict multi-tenant isolation and admin role verification (403 Forbidden for non-admins).
"""

from __future__ import annotations

import logging
from uuid import UUID

import bcrypt
from fastapi import APIRouter, HTTPException, Query as FastQuery, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import selectinload

from app.auth.models import User, UserRole
from app.deps import CurrentUserDep, DbDep
from app.models import Chunk, Document, Feedback, Glossary, IngestionStatus, Query as QueryModel
from app.schemas import (
    AdminAnalyticsOverview,
    AdminChunkItem,
    AdminDocumentDetail,
    AdminDocumentItem,
    AdminDocumentUpdate,
    AdminUserCreate,
    AdminUserItem,
    AdminUserRoleUpdate,
    GlossaryCreate,
    GlossaryItem,
    QueryActivityItem,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8")[:72], salt).decode("utf-8")


def _require_admin(current_user: CurrentUserDep) -> None:
    """Verify that current_user has the admin role."""
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required.",
        )


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/analytics", response_model=AdminAnalyticsOverview)
async def get_analytics(
    db: DbDep,
    current_user: CurrentUserDep,
) -> AdminAnalyticsOverview:
    """Retrieve high-level RAG observability, document statistics, and user feedback metrics."""
    _require_admin(current_user)
    tenant_id = current_user.tenant_id

    # 1. Query Metrics
    total_q_res = await db.execute(
        select(func.count(QueryModel.id)).where(QueryModel.tenant_id == tenant_id)
    )
    total_queries = total_q_res.scalar() or 0

    answered_res = await db.execute(
        select(func.count(QueryModel.id)).where(
            QueryModel.tenant_id == tenant_id,
            QueryModel.answered_or_refused == True,  # noqa: E712
        )
    )
    answered_queries = answered_res.scalar() or 0

    refused_res = await db.execute(
        select(func.count(QueryModel.id)).where(
            QueryModel.tenant_id == tenant_id,
            QueryModel.answered_or_refused == False,  # noqa: E712
        )
    )
    refused_queries = refused_res.scalar() or 0

    avg_conf_res = await db.execute(
        select(func.avg(QueryModel.confidence_score)).where(
            QueryModel.tenant_id == tenant_id,
            QueryModel.confidence_score.is_not(None),
        )
    )
    avg_confidence_val = avg_conf_res.scalar()
    avg_confidence = round(float(avg_confidence_val), 3) if avg_confidence_val is not None else 0.0

    # 2. Feedback Metrics
    feedback_pos_res = await db.execute(
        select(func.count(Feedback.id))
        .join(QueryModel, Feedback.query_id == QueryModel.id)
        .where(
            QueryModel.tenant_id == tenant_id,
            Feedback.thumbs_up_down == True,  # noqa: E712
        )
    )
    pos_feedback = feedback_pos_res.scalar() or 0

    feedback_neg_res = await db.execute(
        select(func.count(Feedback.id))
        .join(QueryModel, Feedback.query_id == QueryModel.id)
        .where(
            QueryModel.tenant_id == tenant_id,
            Feedback.thumbs_up_down == False,  # noqa: E712
        )
    )
    neg_feedback = feedback_neg_res.scalar() or 0

    total_fb = pos_feedback + neg_feedback
    csat_percent = round((pos_feedback / total_fb) * 100.0, 1) if total_fb > 0 else 100.0

    # 3. Documents & Chunks
    doc_count_res = await db.execute(
        select(func.count(Document.id)).where(Document.tenant_id == tenant_id)
    )
    total_docs = doc_count_res.scalar() or 0

    chunk_count_res = await db.execute(
        select(func.count(Chunk.id)).where(Chunk.tenant_id == tenant_id)
    )
    total_chunks = chunk_count_res.scalar() or 0

    # 4. Total Members
    members_count_res = await db.execute(
        select(func.count(User.id)).where(User.tenant_id == tenant_id)
    )
    total_members = members_count_res.scalar() or 0

    # 5. Department Distribution
    dept_res = await db.execute(
        select(Document.department, func.count(Document.id))
        .where(Document.tenant_id == tenant_id)
        .group_by(Document.department)
    )
    department_distribution = {
        (dept or "General"): count for dept, count in dept_res.fetchall()
    }

    # 6. Recent Activity Stream
    recent_q_res = await db.execute(
        select(QueryModel)
        .options(selectinload(QueryModel.feedback))
        .where(QueryModel.tenant_id == tenant_id)
        .order_by(QueryModel.created_at.desc())
        .limit(20)
    )
    queries = recent_q_res.scalars().all()

    recent_activity: list[QueryActivityItem] = []
    for q in queries:
        fb = q.feedback[0] if q.feedback else None
        recent_activity.append(
            QueryActivityItem(
                query_id=q.id,
                raw_query=q.raw_query,
                created_at=q.created_at.isoformat() if q.created_at else "",
                confidence_score=q.confidence_score,
                answered_or_refused=q.answered_or_refused,
                feedback_thumbs_up_down=fb.thumbs_up_down if fb else None,
                feedback_comment=fb.comment if fb else None,
            )
        )

    return AdminAnalyticsOverview(
        total_queries=total_queries,
        answered_queries=answered_queries,
        refused_queries=refused_queries,
        avg_confidence=avg_confidence,
        positive_feedback_count=pos_feedback,
        negative_feedback_count=neg_feedback,
        csat_percent=csat_percent,
        total_documents=total_docs,
        total_chunks=total_chunks,
        total_members=total_members,
        recent_activity=recent_activity,
        department_distribution=department_distribution,
    )


# ── Document Management ───────────────────────────────────────────────────────

@router.get("/documents", response_model=list[AdminDocumentItem])
async def list_documents(
    db: DbDep,
    current_user: CurrentUserDep,
    department: str | None = None,
    doc_type: str | None = None,
    version_status: str | None = None,
    search: str | None = None,
) -> list[AdminDocumentItem]:
    """List all indexed documents for this enterprise with chunk counts."""
    _require_admin(current_user)
    tenant_id = current_user.tenant_id

    # Subquery for chunk counts per document
    chunk_counts_subq = (
        select(Chunk.document_id, func.count(Chunk.id).label("chunk_count"))
        .where(Chunk.tenant_id == tenant_id)
        .group_by(Chunk.document_id)
        .subquery()
    )

    query = (
        select(Document, func.coalesce(chunk_counts_subq.c.chunk_count, 0).label("chunk_count"))
        .outerjoin(chunk_counts_subq, Document.id == chunk_counts_subq.c.document_id)
        .where(Document.tenant_id == tenant_id)
    )

    if department:
        query = query.where(Document.department.ilike(f"%{department}%"))
    if doc_type:
        query = query.where(Document.doc_type.ilike(f"%{doc_type}%"))
    if version_status:
        query = query.where(Document.version_status == version_status)
    if search:
        query = query.where(
            Document.title.ilike(f"%{search}%") | Document.summary.ilike(f"%{search}%")
        )

    query = query.order_by(Document.title.asc())
    results = await db.execute(query)

    items: list[AdminDocumentItem] = []
    for doc, chunk_count in results.all():
        items.append(
            AdminDocumentItem(
                id=doc.id,
                tenant_id=doc.tenant_id,
                title=doc.title,
                department=doc.department,
                doc_type=doc.doc_type,
                effective_date=doc.effective_date,
                version_status=doc.version_status or "current",
                source_path=doc.source_path,
                summary=doc.summary,
                section_tree=doc.section_tree,
                ingestion_status=doc.ingestion_status,
                chunk_count=chunk_count,
            )
        )
    return items


@router.get("/documents/{document_id}", response_model=AdminDocumentDetail)
async def get_document_detail(
    document_id: UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> AdminDocumentDetail:
    """Retrieve detailed information for a specific document, including its chunks and section tree."""
    _require_admin(current_user)
    tenant_id = current_user.tenant_id

    doc_res = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
    )
    doc = doc_res.scalars().first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    chunks_res = await db.execute(
        select(Chunk)
        .where(Chunk.document_id == document_id, Chunk.tenant_id == tenant_id)
        .order_by(Chunk.id.asc())
    )
    chunks = chunks_res.scalars().all()

    chunk_items = [
        AdminChunkItem(
            id=c.id,
            document_id=c.document_id,
            section_path=c.section_path,
            text=c.text,
            department=c.department,
            doc_type=c.doc_type,
            version_status=c.version_status,
        )
        for c in chunks
    ]

    return AdminDocumentDetail(
        id=doc.id,
        tenant_id=doc.tenant_id,
        title=doc.title,
        department=doc.department,
        doc_type=doc.doc_type,
        effective_date=doc.effective_date,
        version_status=doc.version_status or "current",
        source_path=doc.source_path,
        summary=doc.summary,
        section_tree=doc.section_tree,
        ingestion_status=doc.ingestion_status,
        chunk_count=len(chunk_items),
        chunks=chunk_items,
    )


@router.patch("/documents/{document_id}", response_model=AdminDocumentItem)
async def update_document(
    document_id: UUID,
    payload: AdminDocumentUpdate,
    db: DbDep,
    current_user: CurrentUserDep,
) -> AdminDocumentItem:
    """Update metadata for an indexed document (e.g. title, department, doc_type, version_status)."""
    _require_admin(current_user)
    tenant_id = current_user.tenant_id

    doc_res = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
    )
    doc = doc_res.scalars().first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    update_dict = payload.model_dump(exclude_unset=True)
    for field, val in update_dict.items():
        setattr(doc, field, val)

    # Also update chunks metadata if department, doc_type, or version_status changed
    chunk_updates = {}
    if "department" in update_dict:
        chunk_updates["department"] = update_dict["department"]
    if "doc_type" in update_dict:
        chunk_updates["doc_type"] = update_dict["doc_type"]
    if "version_status" in update_dict:
        chunk_updates["version_status"] = update_dict["version_status"]
    if "effective_date" in update_dict:
        chunk_updates["effective_date"] = update_dict["effective_date"]

    if chunk_updates:
        await db.execute(
            update(Chunk)
            .where(Chunk.document_id == document_id, Chunk.tenant_id == tenant_id)
            .values(**chunk_updates)
        )

    await db.commit()
    await db.refresh(doc)

    # Count chunks
    chunk_count_res = await db.execute(
        select(func.count(Chunk.id)).where(Chunk.document_id == document_id)
    )
    chunk_count = chunk_count_res.scalar() or 0

    return AdminDocumentItem(
        id=doc.id,
        tenant_id=doc.tenant_id,
        title=doc.title,
        department=doc.department,
        doc_type=doc.doc_type,
        effective_date=doc.effective_date,
        version_status=doc.version_status or "current",
        source_path=doc.source_path,
        summary=doc.summary,
        section_tree=doc.section_tree,
        ingestion_status=doc.ingestion_status,
        chunk_count=chunk_count,
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> None:
    """Permanently delete a document and all associated chunks."""
    _require_admin(current_user)
    tenant_id = current_user.tenant_id

    doc_res = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
    )
    doc = doc_res.scalars().first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Delete associated chunks
    await db.execute(
        delete(Chunk).where(Chunk.document_id == document_id, Chunk.tenant_id == tenant_id)
    )
    # Delete document record
    await db.delete(doc)
    await db.commit()
    logger.info("Deleted document %s for tenant %s", document_id, tenant_id)


# ── Enterprise Member Management ───────────────────────────────────────────────

@router.get("/users", response_model=list[AdminUserItem])
async def list_users(
    db: DbDep,
    current_user: CurrentUserDep,
) -> list[AdminUserItem]:
    """List all members belonging to the administrator's enterprise."""
    _require_admin(current_user)
    tenant_id = current_user.tenant_id

    res = await db.execute(
        select(User).where(User.tenant_id == tenant_id).order_by(User.email.asc())
    )
    users = res.scalars().all()
    return [
        AdminUserItem(
            id=u.id,
            tenant_id=u.tenant_id,
            email=u.email,
            role=u.role,
        )
        for u in users
    ]


@router.post("/users", response_model=AdminUserItem, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminUserCreate,
    db: DbDep,
    current_user: CurrentUserDep,
) -> AdminUserItem:
    """Create or invite a new member to the enterprise."""
    _require_admin(current_user)
    tenant_id = current_user.tenant_id

    if payload.role not in [UserRole.ADMIN.value, UserRole.MEMBER.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role specified. Must be 'admin' or 'member'.",
        )

    existing_user_res = await db.execute(
        select(User).where(User.email.ilike(payload.email.strip()))
    )
    if existing_user_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{payload.email}' is already registered.",
        )

    hashed_pw = _hash_password(payload.password)
    user = User(
        tenant_id=tenant_id,
        email=payload.email.strip(),
        password_hash=hashed_pw,
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("Admin %s created user %s (%s)", current_user.user_id, user.id, user.role)
    return AdminUserItem(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role=user.role,
    )


@router.patch("/users/{user_id}/role", response_model=AdminUserItem)
async def update_user_role(
    user_id: UUID,
    payload: AdminUserRoleUpdate,
    db: DbDep,
    current_user: CurrentUserDep,
) -> AdminUserItem:
    """Update a user's role (admin or member)."""
    _require_admin(current_user)
    tenant_id = current_user.tenant_id

    if payload.role not in [UserRole.ADMIN.value, UserRole.MEMBER.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Allowed values: 'admin', 'member'.",
        )

    if user_id == current_user.user_id and payload.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot demote your own administrator account.",
        )

    user_res = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    user = user_res.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in this enterprise.",
        )

    user.role = payload.role
    await db.commit()
    await db.refresh(user)

    logger.info("Admin %s updated user %s role to %s", current_user.user_id, user.id, user.role)
    return AdminUserItem(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role=user.role,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: DbDep,
    current_user: CurrentUserDep,
) -> None:
    """Remove a user from the enterprise."""
    _require_admin(current_user)
    tenant_id = current_user.tenant_id

    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove your own administrator account.",
        )

    user_res = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    user = user_res.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    await db.delete(user)
    await db.commit()
    logger.info("Admin %s deleted user %s from tenant %s", current_user.user_id, user_id, tenant_id)


# ── Glossary Management ────────────────────────────────────────────────────────

@router.get("/glossary", response_model=list[GlossaryItem])
async def list_glossary(
    db: DbDep,
    current_user: CurrentUserDep,
) -> list[GlossaryItem]:
    """Retrieve all glossary terms and acronym expansions for the enterprise."""
    _require_admin(current_user)
    tenant_id = current_user.tenant_id

    res = await db.execute(
        select(Glossary)
        .where(Glossary.tenant_id == tenant_id)
        .order_by(Glossary.term.asc())
    )
    entries = res.scalars().all()
    return [
        GlossaryItem(id=g.id, term=g.term, expansion=g.expansion)
        for g in entries
    ]


@router.post("/glossary", response_model=GlossaryItem, status_code=status.HTTP_201_CREATED)
async def add_glossary_term(
    payload: GlossaryCreate,
    db: DbDep,
    current_user: CurrentUserDep,
) -> GlossaryItem:
    """Add a new acronym / technical terminology expansion to the enterprise glossary."""
    _require_admin(current_user)
    tenant_id = current_user.tenant_id

    clean_term = payload.term.strip().upper()
    if not clean_term or not payload.expansion.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Term and expansion cannot be empty.",
        )

    # Check if term already exists
    existing = await db.execute(
        select(Glossary).where(
            Glossary.tenant_id == tenant_id,
            Glossary.term.ilike(clean_term),
        )
    )
    entry = existing.scalars().first()
    if entry:
        entry.expansion = payload.expansion.strip()
    else:
        entry = Glossary(
            tenant_id=tenant_id,
            term=clean_term,
            expansion=payload.expansion.strip(),
        )
        db.add(entry)

    await db.commit()
    await db.refresh(entry)
    return GlossaryItem(id=entry.id, term=entry.term, expansion=entry.expansion)


@router.delete("/glossary/{term}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_glossary_term(
    term: str,
    db: DbDep,
    current_user: CurrentUserDep,
) -> None:
    """Delete a glossary entry for this enterprise."""
    _require_admin(current_user)
    tenant_id = current_user.tenant_id

    await db.execute(
        delete(Glossary).where(
            Glossary.tenant_id == tenant_id,
            Glossary.term.ilike(term.strip()),
        )
    )
    await db.commit()
