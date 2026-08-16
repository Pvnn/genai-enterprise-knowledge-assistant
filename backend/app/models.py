"""Shared ORM models (non-auth).

Owner: P2 (Schema source of truth)
Matches the database schema in Section 4 of the engineering spec (addendum
included).
"""

import enum
import logging
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
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
    section_tree: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Priority 2
    ingestion_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=IngestionStatus.PENDING.value,
        comment="Async ingestion lifecycle: pending|processing|done|failed",
    )

    enterprise: Mapped["Enterprise"] = relationship("Enterprise", back_populates="documents")
