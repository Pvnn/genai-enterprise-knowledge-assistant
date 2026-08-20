"""Add ON DELETE CASCADE to existing foreign keys.

Revision: b1c2d3e4f5a6
Down revision: a1b2c3d4e5f6
"""

from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # users.tenant_id -> enterprises.id
    op.drop_constraint("users_tenant_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key("users_tenant_id_fkey", "users", "enterprises", ["tenant_id"], ["id"], ondelete="CASCADE")

    # documents.tenant_id -> enterprises.id
    op.drop_constraint("documents_tenant_id_fkey", "documents", type_="foreignkey")
    op.create_foreign_key("documents_tenant_id_fkey", "documents", "enterprises", ["tenant_id"], ["id"], ondelete="CASCADE")

    # chunks.document_id -> documents.id
    op.drop_constraint("chunks_document_id_fkey", "chunks", type_="foreignkey")
    op.create_foreign_key("chunks_document_id_fkey", "chunks", "documents", ["document_id"], ["id"], ondelete="CASCADE")

    # chunks.tenant_id -> enterprises.id
    op.drop_constraint("chunks_tenant_id_fkey", "chunks", type_="foreignkey")
    op.create_foreign_key("chunks_tenant_id_fkey", "chunks", "enterprises", ["tenant_id"], ["id"], ondelete="CASCADE")

    # glossary.tenant_id -> enterprises.id
    op.drop_constraint("glossary_tenant_id_fkey", "glossary", type_="foreignkey")
    op.create_foreign_key("glossary_tenant_id_fkey", "glossary", "enterprises", ["tenant_id"], ["id"], ondelete="CASCADE")

    # queries.tenant_id -> enterprises.id
    op.drop_constraint("queries_tenant_id_fkey", "queries", type_="foreignkey")
    op.create_foreign_key("queries_tenant_id_fkey", "queries", "enterprises", ["tenant_id"], ["id"], ondelete="CASCADE")

    # queries.user_id -> users.id
    op.drop_constraint("queries_user_id_fkey", "queries", type_="foreignkey")
    op.create_foreign_key("queries_user_id_fkey", "queries", "users", ["user_id"], ["id"], ondelete="CASCADE")

    # feedback.query_id -> queries.id
    op.drop_constraint("feedback_query_id_fkey", "feedback", type_="foreignkey")
    op.create_foreign_key("feedback_query_id_fkey", "feedback", "queries", ["query_id"], ["id"], ondelete="CASCADE")

    # conversations.tenant_id -> enterprises.id
    op.drop_constraint("conversations_tenant_id_fkey", "conversations", type_="foreignkey")
    op.create_foreign_key("conversations_tenant_id_fkey", "conversations", "enterprises", ["tenant_id"], ["id"], ondelete="CASCADE")

    # conversations.user_id -> users.id
    op.drop_constraint("conversations_user_id_fkey", "conversations", type_="foreignkey")
    op.create_foreign_key("conversations_user_id_fkey", "conversations", "users", ["user_id"], ["id"], ondelete="CASCADE")

    # messages.tenant_id -> enterprises.id
    op.drop_constraint("messages_tenant_id_fkey", "messages", type_="foreignkey")
    op.create_foreign_key("messages_tenant_id_fkey", "messages", "enterprises", ["tenant_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    # messages.tenant_id
    op.drop_constraint("messages_tenant_id_fkey", "messages", type_="foreignkey")
    op.create_foreign_key("messages_tenant_id_fkey", "messages", "enterprises", ["tenant_id"], ["id"])

    # conversations.user_id
    op.drop_constraint("conversations_user_id_fkey", "conversations", type_="foreignkey")
    op.create_foreign_key("conversations_user_id_fkey", "conversations", "users", ["user_id"], ["id"])

    # conversations.tenant_id
    op.drop_constraint("conversations_tenant_id_fkey", "conversations", type_="foreignkey")
    op.create_foreign_key("conversations_tenant_id_fkey", "conversations", "enterprises", ["tenant_id"], ["id"])

    # feedback.query_id
    op.drop_constraint("feedback_query_id_fkey", "feedback", type_="foreignkey")
    op.create_foreign_key("feedback_query_id_fkey", "feedback", "queries", ["query_id"], ["id"])

    # queries.user_id
    op.drop_constraint("queries_user_id_fkey", "queries", type_="foreignkey")
    op.create_foreign_key("queries_user_id_fkey", "queries", "users", ["user_id"], ["id"])

    # queries.tenant_id
    op.drop_constraint("queries_tenant_id_fkey", "queries", type_="foreignkey")
    op.create_foreign_key("queries_tenant_id_fkey", "queries", "enterprises", ["tenant_id"], ["id"])

    # glossary.tenant_id
    op.drop_constraint("glossary_tenant_id_fkey", "glossary", type_="foreignkey")
    op.create_foreign_key("glossary_tenant_id_fkey", "glossary", "enterprises", ["tenant_id"], ["id"])

    # chunks.tenant_id
    op.drop_constraint("chunks_tenant_id_fkey", "chunks", type_="foreignkey")
    op.create_foreign_key("chunks_tenant_id_fkey", "chunks", "enterprises", ["tenant_id"], ["id"])

    # chunks.document_id
    op.drop_constraint("chunks_document_id_fkey", "chunks", type_="foreignkey")
    op.create_foreign_key("chunks_document_id_fkey", "chunks", "documents", ["document_id"], ["id"])

    # documents.tenant_id
    op.drop_constraint("documents_tenant_id_fkey", "documents", type_="foreignkey")
    op.create_foreign_key("documents_tenant_id_fkey", "documents", "enterprises", ["tenant_id"], ["id"])

    # users.tenant_id
    op.drop_constraint("users_tenant_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key("users_tenant_id_fkey", "users", "enterprises", ["tenant_id"], ["id"])
