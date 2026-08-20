/**
 * Typed API client for the backend.
 * Owner: P7
 *
 * Implements:
 *   - POST /chat (SSE stream parser for token, clarify, and final events)
 *   - POST /feedback (Priority 2 feedback capture)
 *   - POST /auth/login (Auth helper)
 *   - GET  /auth/me (Auth helper)
 *   - fetchDocuments (Document library helper)
 *
 * All request/response shapes strictly match Section 5 of the engineering spec.
 */

import {
  ChatRequest,
  ClarifyEvent,
  CurrentUser,
  DocumentItem,
  DocumentStatusResponse,
  ErrorResponse,
  FeedbackRequest,
  FeedbackResponse,
  FinalEvent,
  LoginRequest,
  LoginResponse,
  RegisterEnterpriseRequest,
  RegisterEnterpriseResponse,
  RegisterUserRequest,
  RegisterUserResponse,
  TokenEvent,
  UploadResponse,
} from "../chat/types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem("access_token");
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}


/**
 * Stream a chat completion from POST /chat using Server-Sent Events.
 * If the backend is offline or unreachable, seamlessly falls back to demo simulation
 * so users can explore and evaluate the interface.
 */
export async function streamChat(
  request: ChatRequest,
  callbacks: {
    onToken?: (event: TokenEvent) => void;
    onClarify?: (event: ClarifyEvent) => void;
    onFinal?: (event: FinalEvent) => void;
    onError?: (error: ErrorResponse | Error) => void;
  },
  signal?: AbortSignal
): Promise<void> {
  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeader(),
      },
      body: JSON.stringify(request),
      signal,
    });

    if (!response.ok) {
      if (response.status === 401) {
        window.dispatchEvent(new Event("auth_error"));
      }
      let errorData: ErrorResponse;
      try {
        errorData = await response.json();
      } catch {
        errorData = {
          error: "http_error",
          detail: `Server responded with status ${response.status}: ${response.statusText}`,
        };
      }
      callbacks.onError?.(errorData);
      return;
    }

    if (!response.body) {
      callbacks.onError?.({
        error: "stream_error",
        detail: "Response body is empty or readable stream is unavailable.",
      });
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    let isReading = true;
    while (isReading) {
      const { value, done } = await reader.read();
      if (done) {
        isReading = false;
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        const dataPrefix = "data:";
        if (trimmed.startsWith(dataPrefix)) {
          const rawJson = trimmed.slice(dataPrefix.length).trim();
          if (!rawJson) continue;

          try {
            const parsed = JSON.parse(rawJson);
            if (parsed.type === "token") {
              callbacks.onToken?.(parsed as TokenEvent);
            } else if (parsed.type === "clarify") {
              callbacks.onClarify?.(parsed as ClarifyEvent);
            } else if (parsed.type === "final") {
              callbacks.onFinal?.(parsed as FinalEvent);
            }
          } catch (jsonErr) {
            console.warn("Failed to parse SSE line JSON:", rawJson, jsonErr);
          }
        }
      }
    }

    if (buffer.trim().startsWith("data:")) {
      const rawJson = buffer.trim().slice(5).trim();
      try {
        const parsed = JSON.parse(rawJson);
        if (parsed.type === "token") {
          callbacks.onToken?.(parsed as TokenEvent);
        } else if (parsed.type === "clarify") {
          callbacks.onClarify?.(parsed as ClarifyEvent);
        } else if (parsed.type === "final") {
          callbacks.onFinal?.(parsed as FinalEvent);
        }
      } catch (jsonErr) {
        console.warn("Failed to parse trailing SSE line:", buffer, jsonErr);
      }
    }
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      return;
    }
    callbacks.onError?.({ error: "http_error", detail: "Backend unreachable" });
  }
}

/**
 * Submit feedback for an answer (Priority 2).
 * Strictly calls POST /feedback per Section 5 API contract.
 */
export async function submitFeedback(
  request: FeedbackRequest
): Promise<FeedbackResponse> {
  const response = await fetch(`${API_BASE}/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    let errorData: ErrorResponse;
    try {
      errorData = await response.json();
    } catch {
      errorData = {
        error: "feedback_failed",
        detail: `Server responded with status ${response.status}`,
      };
    }
    throw new Error(errorData.detail || errorData.error);
  }

  return response.json();
}

let cachedDocuments: DocumentItem[] | null = null;
let lastTenantId: string | null = null;

export function invalidateDocumentsCache() {
  cachedDocuments = null;
}

/**
 * Fetch list of indexed documents for the institutional knowledge library.
 */
export async function fetchDocuments(tenant_id: string, forceRefetch = false): Promise<DocumentItem[]> {
  if (!forceRefetch && cachedDocuments && lastTenantId === tenant_id) {
    return cachedDocuments;
  }

  const response = await fetch(`${API_BASE}/documents?tenant_id=${tenant_id}`, {
    headers: {
      ...getAuthHeader(),
    },
  });

  if (response.status === 401) {
    window.dispatchEvent(new Event("auth_error"));
    throw new Error("Unauthorized");
  }

  if (response.ok) {
    const data = await response.json();
    cachedDocuments = data;
    lastTenantId = tenant_id;
    return data;
  }

  throw new Error("Failed to fetch documents");
}

/**
 * Authenticate user and retrieve JWT access token (Section 5).
 * TODO: confirm with P6 whether auth/* already exposes these via a hook or client helper.
 */
export async function login(request: LoginRequest): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    let errorData: ErrorResponse;
    try {
      errorData = await response.json();
    } catch {
      errorData = {
        error: "auth_failed",
        detail: `Login failed with status ${response.status}`,
      };
    }
    throw new Error(errorData.detail || errorData.error);
  }

  return response.json();
}

/**
 * Fetch current authenticated user identity (Section 5).
 * TODO: confirm with P6 whether auth/* already exposes these via a hook or client helper.
 */
export async function getMe(): Promise<CurrentUser> {
  const response = await fetch(`${API_BASE}/auth/me`, {
    method: "GET",
    headers: {
      ...getAuthHeader(),
    },
  });

  if (!response.ok) {
    let errorData: ErrorResponse;
    try {
      errorData = await response.json();
    } catch {
      errorData = {
        error: "me_failed",
        detail: `Failed to fetch identity with status ${response.status}`,
      };
    }
    throw new Error(errorData.detail || errorData.error);
  }

  return response.json();
}

/**
 * Register a new enterprise tenant.
 * POST /auth/register/enterprise
 */
export async function registerEnterprise(
  request: RegisterEnterpriseRequest
): Promise<RegisterEnterpriseResponse> {
  const response = await fetch(`${API_BASE}/auth/register/enterprise`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    let errorData: ErrorResponse;
    try {
      errorData = await response.json();
    } catch {
      errorData = {
        error: "registration_failed",
        detail: `Enterprise registration failed with status ${response.status}`,
      };
    }
    throw new Error(errorData.detail || errorData.error);
  }

  return response.json();
}

/**
 * Register a new user under an enterprise tenant.
 * POST /auth/register/user
 */
export async function registerUser(
  request: RegisterUserRequest
): Promise<RegisterUserResponse> {
  const response = await fetch(`${API_BASE}/auth/register/user`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    let errorData: ErrorResponse;
    try {
      errorData = await response.json();
    } catch {
      errorData = {
        error: "registration_failed",
        detail: `User registration failed with status ${response.status}`,
      };
    }
    throw new Error(errorData.detail || errorData.error);
  }

  return response.json();
}


/**
 * Upload a PDF document for ingestion (Admin only).
 * Strictly calls POST /documents/upload using FormData per Section 5 addendum.
 */
export async function uploadDocument(
  file: File,
  department: string,
  docType: string
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("department", department.trim());
  formData.append("doc_type", docType.trim());

  const response = await fetch(`${API_BASE}/documents/upload`, {
    method: "POST",
    headers: {
      ...getAuthHeader(),
    },
    body: formData,
  });

  if (!response.ok) {
    let errorData: ErrorResponse;
    try {
      errorData = await response.json();
    } catch {
      errorData = {
        error: "upload_failed",
        detail: `Upload failed with status ${response.status}: ${response.statusText}`,
      };
    }
    throw new Error(errorData.detail || errorData.error);
  }

  invalidateDocumentsCache();
  return response.json();
}

/**
 * Check / poll ingestion status for a document.
 * Strictly calls GET /documents/{documentId}/status per Section 5 addendum.
 */
export async function getDocumentStatus(
  documentId: string
): Promise<DocumentStatusResponse> {
  const response = await fetch(`${API_BASE}/documents/${documentId}/status`, {
    method: "GET",
    headers: {
      ...getAuthHeader(),
    },
  });

  if (!response.ok) {
    let errorData: ErrorResponse;
    try {
      errorData = await response.json();
    } catch {
      errorData = {
        error: "status_check_failed",
        detail: `Status check failed with status ${response.status}`,
      };
    }
    throw new Error(errorData.detail || errorData.error);
  }

  return response.json();
}

export async function fetchConversations() {
  const response = await fetch(`${API_BASE}/conversations`, {
    headers: { ...getAuthHeader() },
  });
  if (response.status === 401) window.dispatchEvent(new Event("auth_error"));
  if (!response.ok) throw new Error("Failed to fetch conversations");
  return response.json();
}

export async function fetchConversationDetail(id: string) {
  const response = await fetch(`${API_BASE}/conversations/${id}`, {
    headers: { ...getAuthHeader() },
  });
  if (response.status === 401) window.dispatchEvent(new Event("auth_error"));
  if (!response.ok) throw new Error("Failed to fetch conversation");
  return response.json();
}

export async function createConversation(title: string) {
  const response = await fetch(`${API_BASE}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeader() },
    body: JSON.stringify({ title }),
  });
  if (response.status === 401) window.dispatchEvent(new Event("auth_error"));
  if (!response.ok) throw new Error("Failed to create conversation");
  return response.json();
}

export async function deleteConversationApi(id: string) {
  const response = await fetch(`${API_BASE}/conversations/${id}`, {
    method: "DELETE",
    headers: { ...getAuthHeader() },
  });
  if (response.status === 401) window.dispatchEvent(new Event("auth_error"));
  if (!response.ok) throw new Error("Failed to delete conversation");
  return response.json();
}

export async function appendMessageApi(conversationId: string, message: any) {
  const response = await fetch(`${API_BASE}/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeader() },
    body: JSON.stringify(message),
  });
  if (response.status === 401) window.dispatchEvent(new Event("auth_error"));
  if (!response.ok) throw new Error("Failed to append message");
  return response.json();
}

export { API_BASE };

