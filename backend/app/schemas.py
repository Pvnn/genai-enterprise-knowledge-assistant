"""Pydantic models for all structured data crossing function/API boundaries.

Owner: P2
Every other module imports Pydantic models from HERE; no raw dicts cross
module or API boundaries.  These shapes must match Sections 4, 5, and 6 of
the engineering spec exactly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Shared error envelope (Section 5) ────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Shared error envelope returned by every API endpoint on failure."""

    error: str
    detail: str


# ── Auth (Section 5) ─────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str
    tenant_code: str


class LoginResponse(BaseModel):
    access_token: str
    tenant_id: UUID
    user_id: UUID
    role: str


class RegisterEnterpriseRequest(BaseModel):
    enterprise_name: str
    admin_email: str
    admin_password: str


class RegisterUserRequest(BaseModel):
    tenant_code: str
    email: str
    password: str


class CurrentUser(BaseModel):
    """Populated by security.get_current_user(); threaded through all requests."""

    user_id: UUID
    tenant_id: UUID
    email: str
    role: str


# ── Retrieval (Section 5 & 6) ─────────────────────────────────────────────────

class MetadataFilters(BaseModel):
    """Optional hard-constraint filters applied at the pgvector search level."""

    department: str | None = None
    doc_type: str | None = None
    version_status: str | None = None


class ScopedSection(BaseModel):
    """A (document_id, section_path) pair returned by Stage 2 routing."""

    document_id: UUID
    section_path: str


class RetrieveRequest(BaseModel):
    query: str
    tenant_id: UUID
    top_k: int = Field(25, ge=1, le=100)
    filters: MetadataFilters = Field(default_factory=MetadataFilters)
    scoped_sections: list[ScopedSection] | None = None


class ChunkResult(BaseModel):
    """A single chunk returned by dense or hybrid retrieval."""

    chunk_id: UUID
    document_id: UUID
    text: str
    section_path: str
    score: float
    department: str | None = None
    doc_type: str | None = None
    effective_date: str | None = None
    version_status: str | None = None
    source_path: str | None = None


class RetrieveResponse(BaseModel):
    chunks: list[ChunkResult]


# ── Query rewriter (Section 6) ────────────────────────────────────────────────

class RewriteResult(BaseModel):
    """Output of query_rewriter.rewrite()."""

    expanded_query: str
    metadata_filters: MetadataFilters
    bm25_variant: str
    dense_variant: str
    sub_queries: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarifying_question: str | None = None


# ── Grounding / generation (Section 5 & 6) ───────────────────────────────────

class Citation(BaseModel):
    chunk_id: UUID
    document_id: UUID
    section_path: str
    source_path: str | None = None


class RefusalDecision(BaseModel):
    """Output of grounding.decide_refusal()."""

    refused: bool
    reason: str | None = None
    confidence: float
    conflict: bool = False


class ConflictResult(BaseModel):
    """Output of conflict_detector.check_conflict()."""

    conflict: bool
    conflicting_chunks: list[ChunkResult] = Field(default_factory=list)


class ChatRequest(BaseModel):
    query: str
    tenant_id: UUID
    conversation_id: str | None = None


# SSE event payloads

class TokenEvent(BaseModel):
    type: str = "token"
    content: str


class ClarifyEvent(BaseModel):
    type: str = "clarify"
    question: str


class FinalEvent(BaseModel):
    type: str = "final"
    answer: str
    citations: list[Citation]
    confidence: float
    refused: bool
    refusal_reason: str | None = None
    conflict: bool = False


# ── Feedback (Section 5) ──────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    query_id: UUID
    thumbs_up_down: bool
    comment: str | None = None


class FeedbackResponse(BaseModel):
    status: str = "ok"


# ── DB row shapes (Section 4) ─────────────────────────────────────────────────

class ChunkDB(BaseModel):
    """Internal representation of a chunks table row."""

    id: UUID
    document_id: UUID
    tenant_id: UUID
    text: str
    section_path: str
    department: str | None = None
    doc_type: str | None = None
    effective_date: str | None = None
    version_status: str | None = None
    source_path: str | None = None


# ── Ingestion upload / status (addendum Section 5) ───────────────────────────

class IngestionStatus(str):
    """Valid values for documents.ingestion_status (addendum Section 4)."""
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class UploadResponse(BaseModel):
    """Response from POST /documents/upload."""

    document_id: UUID
    ingestion_status: str  # one of IngestionStatus values


class DocumentStatusResponse(BaseModel):
    """Response from GET /documents/{document_id}/status."""

    document_id: UUID
    ingestion_status: str  # one of IngestionStatus values
    detail: str | None = None  # human-readable note, e.g. failure reason


# ── Conversation threads & messages ──────────────────────────────────────────

class MessageCreate(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    citations: list[Citation] | list[dict] | None = None
    confidence: float | None = None
    refused: bool = False
    refusal_reason: str | None = None


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    citations: list[dict] | list[Citation] | None = None
    confidence: float | None = None
    refused: bool = False
    refusal_reason: str | None = None
    created_at: datetime


class ConversationCreate(BaseModel):
    title: str | None = "New Conversation"


class ConversationUpdate(BaseModel):
    title: str


class ConversationSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ConversationDetail(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = Field(default_factory=list)
