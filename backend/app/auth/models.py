"""Auth SQLAlchemy ORM models.

Owner: P6 (User/Enterprise)
Matches the database schema in Section 4 of the engineering spec (addendum
included).

Role enum note:
  users.role is constrained to 'admin' | 'member'.
  'admin' is ALWAYS per-tenant — it confers no cross-tenant privileges.
  Every role check in application code MUST also scope by tenant_id.
"""

import enum
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

logger = logging.getLogger(__name__)


class UserRole(str, enum.Enum):
    """Valid values for users.role.

    'admin'  – may upload documents and manage tenant content.
               Per-tenant only; does NOT grant cross-tenant access.
    'member' – standard user; may query but not upload.
    """

    ADMIN = "admin"
    MEMBER = "member"


class Enterprise(Base):
    """enterprises table."""

    __tablename__ = "enterprises"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    users: Mapped[list["User"]] = relationship("User", back_populates="enterprise", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="enterprise", cascade="all, delete-orphan")


class User(Base):
    """users table.

    role is constrained to UserRole enum values at both the ORM and DB level.
    Default is 'member' — admin accounts must be explicitly created.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'member')", name="ck_users_role"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=UserRole.MEMBER.value,
        comment="Per-tenant role: 'admin' or 'member'. Never cross-tenant.",
    )

    enterprise: Mapped[Enterprise] = relationship("Enterprise", back_populates="users")

