"""Initial schema – all tables as defined in spec Section 4.

Owner: P2
Revision: a1b2c3d4e5f6
Down revision: None  (this IS the base migration; there is no prior revision)

Tables created:
  enterprises, users, documents (incl. ingestion_status), chunks, glossary,
  queries, feedback

Schema notes:
  - users.role is constrained to ('admin', 'member') at the DB level.
    'admin' is a per-tenant admin; it confers no cross-tenant privileges.
    The NOT NULL + CHECK constraint means every user must have an explicit role.
  - documents.ingestion_status tracks the async upload pipeline lifecycle.
    Values: 'pending' | 'processing' | 'done' | 'failed'.
  - pgvector's `vector(768)` type is used for chunks.embedding (Gemini embeddings).
    On PostgreSQL / Neon, the pgvector extension is enabled and the column is
    altered to vector(768). On SQLite (in-memory tests), it remains Text.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None

# Valid values for users.role – per-tenant admin, not cross-tenant superuser.
ROLE_CHECK = "role IN ('admin', 'member')"

# Valid values for documents.ingestion_status.
INGESTION_STATUS_CHECK = "ingestion_status IN ('pending', 'processing', 'done', 'failed')"


def upgrade() -> None:
    op.create_table(
        "enterprises",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("enterprises.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.String(10),
            nullable=False,
            comment="Per-tenant role. 'admin' allows document upload within their tenant only.",
        ),
        sa.CheckConstraint(ROLE_CHECK, name="ck_users_role"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("enterprises.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("department", sa.String(255), nullable=True),
        sa.Column("doc_type", sa.String(100), nullable=True),
        sa.Column("effective_date", sa.String(50), nullable=True),
        sa.Column("version_status", sa.String(50), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True, comment="Priority 2 (Stage 0)"),
        sa.Column("section_tree", sa.JSON(), nullable=True, comment="Priority 2 (Stage 0)"),
        sa.Column(
            "ingestion_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="Async ingestion lifecycle: pending|processing|done|failed",
        ),
        sa.CheckConstraint(INGESTION_STATUS_CHECK, name="ck_documents_ingestion_status"),
    )
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("enterprises.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("section_path", sa.String(500), nullable=False),
        # embedding column: vector(768) for gemini-embedding-001.
        # Added as plain Text here so the migration runs on SQLite in tests;
        # altered to vector(768) on PostgreSQL below.
        sa.Column("embedding", sa.Text(), nullable=True, comment="pgvector vector(768)"),
        sa.Column("text_search", sa.Text(), nullable=True, comment="tsvector for BM25"),
        sa.Column("department", sa.String(255), nullable=True),
        sa.Column("doc_type", sa.String(100), nullable=True),
        sa.Column("effective_date", sa.String(50), nullable=True),
        sa.Column("version_status", sa.String(50), nullable=True),
    )
    op.create_index("ix_chunks_tenant_id", "chunks", ["tenant_id"])
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])

    op.create_table(
        "glossary",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("enterprises.id"), nullable=False),
        sa.Column("term", sa.String(255), nullable=False),
        sa.Column("expansion", sa.Text(), nullable=False),
        comment="Priority 2 (Stage 0) – auto-built acronym/entity glossary",
    )
    op.create_index("ix_glossary_tenant_id", "glossary", ["tenant_id"])

    op.create_table(
        "queries",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("enterprises.id"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("raw_query", sa.Text(), nullable=False),
        sa.Column("rewritten_query", sa.Text(), nullable=True),
        sa.Column("routed_doc_ids", sa.JSON(), nullable=True),
        sa.Column("retrieved_chunk_ids", sa.JSON(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("answered_or_refused", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_queries_tenant_id", "queries", ["tenant_id"])

    op.create_table(
        "feedback",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("query_id", sa.UUID(), sa.ForeignKey("queries.id"), nullable=False),
        sa.Column("thumbs_up_down", sa.Boolean(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
    )

    bind = op.get_bind()
    if bind and bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        op.execute("ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(768) USING embedding::vector;")


def downgrade() -> None:
    op.drop_table("feedback")
    op.drop_table("queries")
    op.drop_table("glossary")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("users")
    op.drop_table("enterprises")