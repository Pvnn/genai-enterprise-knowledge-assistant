/**
 * TypeScript definitions for Chat UI, SSE Streaming, Citations, Feedback, and Document Library.
 * Owner: P7
 *
 * Strictly adheres to Section 5 and Section 6 of the Engineering Spec.
 * All API boundaries and event payloads match backend schemas exactly.
 */

/**
 * Citation payload strictly matching Section 5 /chat final event.
 * Only includes chunk_id, document_id, section_path, source_path.
 */
export interface Citation {
  chunk_id: string;
  document_id: string;
  section_path: string;
  source_path?: string | null;
}

/**
 * SSE Token event streamed during answer generation.
 */
export interface TokenEvent {
  type: "token";
  content: string;
}

/**
 * SSE Clarify event streamed when query rewriter requires role/department signal.
 */
export interface ClarifyEvent {
  type: "clarify";
  question: string;
}

/**
 * SSE Final event carrying full grounded answer, citations, confidence, refusal, and conflict flags.
 */
export interface FinalEvent {
  type: "final";
  answer: string;
  citations: Citation[];
  confidence: number;
  refused: boolean;
  refusal_reason?: string | null;
  conflict: boolean;
}

/**
 * Discriminated union of SSE events from POST /chat.
 */
export type SSEEvent = TokenEvent | ClarifyEvent | FinalEvent;

/**
 * Request payload for POST /chat (Section 5).
 */
export interface ChatRequest {
  query: string;
  tenant_id: string;
  conversation_id?: string | null;
}

/**
 * Request payload for POST /feedback (Section 5).
 */
export interface FeedbackRequest {
  query_id: string;
  thumbs_up_down: boolean;
  comment?: string | null;
}

/**
 * Response payload for POST /feedback (Section 5).
 */
export interface FeedbackResponse {
  status: string;
}

/**
 * Shared error envelope returned by all API endpoints on failure (Section 5).
 */
export interface ErrorResponse {
  error: string;
  detail: string;
}

/**
 * Authentication login request (Section 5).
 */
export interface LoginRequest {
  email: string;
  password: string;
  tenant_code: string;
}

/**
 * Authentication login response (Section 5).
 */
export interface LoginResponse {
  access_token: string;
  tenant_id: string;
  user_id: string;
  role: string;
}

/**
 * Current user identity from GET /auth/me (Section 5).
 */
export interface CurrentUser {
  user_id: string;
  tenant_id: string;
  email: string;
  role: string;
}

/**
 * Institutional document representation for the Document Library view.
 * Matches Section 4 documents schema.
 */
export interface DocumentItem {
  id: string;
  tenant_id: string;
  title: string;
  department: string;
  doc_type: string;
  effective_date: string;
  version_status: "current" | "superseded" | "draft";
  source_path?: string | null;
  summary?: string | null;
  chunk_count?: number;
  ingestion_status?: "done" | "processing" | "pending" | "failed";
}

/**
 * Ingestion upload response (Section 5 addendum).
 */
export interface UploadResponse {
  document_id: string;
  ingestion_status: string;
}

/**
 * Document ingestion status response (Section 5 addendum).
 */
export interface DocumentStatusResponse {
  document_id: string;
  ingestion_status: string;
  detail?: string | null;
}

/**
 * Message state within the frontend Chat UI.
 */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: "streaming" | "done" | "error";
  clarify?: ClarifyEvent;
  final?: FinalEvent;
  errorDetail?: string;
  timestamp: string;
  feedbackSubmitted?: "up" | "down" | null;
}

/**
 * Conversation thread state for the chat history sidebar.
 */
export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
}

