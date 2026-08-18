"""Shared ORM models (non-auth).

Owner: P2 (Schema source of truth)
Matches the database schema in Section 4 of the engineering spec (addendum
included).
"""

from __future__ import annotations

import enum
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

logger = logging.getLogger(__name__)


class IngestionStatus(str, enum.Enum):
    """Valid values for documents.ingestion_status."""

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Document(Base):
    """documents table.

    ingestion_status tracks the async upload pipeline:
      pending → processing → done | failed
    """

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "ingestion_status IN ('pending', 'processing', 'done', 'failed')",
            name="ck_documents_ingestion_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("enterprises.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    doc_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    version_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)         # Priority 2
    section_tree: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # Priority 2
    ingestion_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=IngestionStatus.PENDING.value,
        comment="Async ingestion lifecycle: pending|processing|done|failed",
    )

    enterprise: Mapped[Enterprise] = relationship("Enterprise", back_populates="documents")
    chunks: Mapped[list[Chunk]] = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    """chunks table."""

    __tablename__ = "chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("enterprises.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    section_path: Mapped[str] = mapped_column(String(500), nullable=False)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True, comment="pgvector vector(768)")
    text_search: Mapped[str | None] = mapped_column(Text, nullable=True, comment="tsvector for BM25")
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    doc_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    version_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    document: Mapped[Document] = relationship("Document", back_populates="chunks")


class Glossary(Base):
    """glossary table."""

    __tablename__ = "glossary"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("enterprises.id"), nullable=False)
    term: Mapped[str] = mapped_column(String(255), nullable=False)
    expansion: Mapped[str] = mapped_column(Text, nullable=False)


class Query(Base):
    """queries table."""

    __tablename__ = "queries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("enterprises.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    raw_query: Mapped[str] = mapped_column(Text, nullable=False)
    rewritten_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    routed_doc_ids: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    retrieved_chunk_ids: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    answered_or_refused: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    feedback: Mapped[list[Feedback]] = relationship("Feedback", back_populates="query")


class Feedback(Base):
    """feedback table."""

    __tablename__ = "feedback"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    query_id: Mapped[UUID] = mapped_column(ForeignKey("queries.id"), nullable=False)
    thumbs_up_down: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    query: Mapped[Query] = relationship("Query", back_populates="feedback")
