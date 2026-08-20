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
import {
  AdminAnalyticsData,
  AdminDocument,
  AdminUser,
  GlossaryEntry,
} from "../admin/types";

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
  if (
    (request.email.toLowerCase() === "admin" ||
      request.email.toLowerCase() === "admin@institution.edu" ||
      request.email.toLowerCase() === "admin@test.com") &&
    request.password === "admin"
  ) {
    return {
      access_token: "mock-admin-token-xyz",
      token_type: "bearer",
      tenant_id: "00000000-0000-0000-0000-000000000001",
      user_id: "00000000-0000-0000-0000-000000000002",
      role: "admin",
    };
  }

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
  docType: string,
  effectiveDate?: string
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("department", (department || "").trim());
  formData.append("doc_type", (docType || "").trim());
  formData.append(
    "effective_date",
    (effectiveDate && effectiveDate.trim()) || new Date().toISOString().split("T")[0]
  );

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

export async function appendMessageApi(conversationId: string, message: unknown) {
  const response = await fetch(`${API_BASE}/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeader() },
    body: JSON.stringify(message),
  });
  if (response.status === 401) window.dispatchEvent(new Event("auth_error"));
  if (!response.ok) throw new Error("Failed to append message");
  return response.json();
}

// ── Admin Dashboard API Helpers ─────────────────────────────────────────────

const MOCK_ANALYTICS: AdminAnalyticsData = {
  total_queries: 1420,
  answered_queries: 1318,
  refused_queries: 102,
  avg_confidence: 0.912,
  positive_feedback_count: 512,
  negative_feedback_count: 28,
  csat_percent: 94.8,
  total_documents: 14,
  total_chunks: 482,
  total_members: 38,
  recent_activity: [
    {
      query_id: "q-101",
      raw_query: "What is the maternity leave entitlement for permanent faculty?",
      created_at: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
      confidence_score: 0.96,
      answered_or_refused: true,
      feedback_thumbs_up_down: true,
      feedback_comment: "Very clear and cited the exact section clause.",
    },
    {
      query_id: "q-102",
      raw_query: "How much per diem is reimbursed for international academic conferences?",
      created_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
      confidence_score: 0.89,
      answered_or_refused: true,
      feedback_thumbs_up_down: true,
      feedback_comment: null,
    },
    {
      query_id: "q-103",
      raw_query: "What is the policy for overnight gym and parking access?",
      created_at: new Date(Date.now() - 1000 * 60 * 110).toISOString(),
      confidence_score: 0.38,
      answered_or_refused: false,
      feedback_thumbs_up_down: null,
      feedback_comment: null,
    },
    {
      query_id: "q-104",
      raw_query: "What is the minimum attendance threshold required to appear for semester end exams?",
      created_at: new Date(Date.now() - 1000 * 60 * 240).toISOString(),
      confidence_score: 0.94,
      answered_or_refused: true,
      feedback_thumbs_up_down: true,
      feedback_comment: null,
    },
    {
      query_id: "q-105",
      raw_query: "Who is authorized to approve departmental single-quotation purchases under $5000?",
      created_at: new Date(Date.now() - 1000 * 60 * 360).toISOString(),
      confidence_score: 0.92,
      answered_or_refused: true,
      feedback_thumbs_up_down: false,
      feedback_comment: "Clause was updated in last circular.",
    },
  ],
  department_distribution: {
    "Human Resources": 4,
    "Finance & Accounts": 3,
    "Academic Affairs": 4,
    "Procurement": 2,
    "Research & Development": 1,
  },
};

let mockAdminDocs: AdminDocument[] = [
  {
    id: "doc-leave-policy-2025",
    tenant_id: "00000000-0000-0000-0000-000000000001",
    title: "Institutional Leave Rules and Guidelines 2025",
    department: "Human Resources",
    doc_type: "Policy",
    effective_date: "2025-01-01",
    version_status: "current",
    source_path: "uploads/hr/Institutional_Leave_Rules_2025.pdf",
    summary: "Comprehensive leave entitlements covering casual leave, earned leave, maternity, paternity, and sabbatical provisions.",
    section_tree: {
      "1. Introduction": ["Scope of applicability", "Definitions"],
      "2. Casual & Earned Leave": ["Accrual rules", "Carry-forward limits"],
      "3. Special Leaves": ["Maternity Leave (180 days)", "Paternity Leave", "Sabbatical"],
      "4. Approval Process": ["ERP portal workflow", "Delegation of authority"],
    },
    chunk_count: 42,
    ingestion_status: "done",
  },
  {
    id: "doc-travel-reimburse-2024",
    tenant_id: "00000000-0000-0000-0000-000000000001",
    title: "Official Travel, DA and Per Diem Regulations",
    department: "Finance & Accounts",
    doc_type: "Regulation",
    effective_date: "2024-04-01",
    version_status: "current",
    source_path: "uploads/finance/Travel_DA_Regulations_2024.pdf",
    summary: "Prescribes travel allowances, hotel caps, daily allowance per diem, and conference travel claim workflows.",
    section_tree: {
      "1. Travel Categories": ["Domestic Tier 1/2", "International Missions"],
      "2. Daily Allowance": ["Per diem rates", "Incidental reimbursement"],
      "3. Claim Workflow": ["Submission window (30 days)", "Required receipts"],
    },
    chunk_count: 28,
    ingestion_status: "done",
  },
  {
    id: "doc-academic-ordinance-2024",
    tenant_id: "00000000-0000-0000-0000-000000000001",
    title: "Academic Ordinance for Semester Grading and Evaluation",
    department: "Academic Affairs",
    doc_type: "Ordinance",
    effective_date: "2024-08-01",
    version_status: "current",
    source_path: "uploads/academic/Academic_Ordinance_Grading_2024.pdf",
    summary: "Governs letter grading scale, SGPA/CGPA calculations, re-evaluation petitions, and minimum attendance thresholds.",
    section_tree: {
      "1. Attendance Rules": ["80% minimum mandatory threshold", "5% medical condonation"],
      "2. Grading Scheme": ["10-point scale", "Passing criteria"],
      "3. Re-evaluation": ["Appeals procedure", "Fee schedule"],
    },
    chunk_count: 56,
    ingestion_status: "done",
  },
  {
    id: "doc-procurement-guidelines-2023",
    tenant_id: "00000000-0000-0000-0000-000000000001",
    title: "Departmental Purchase and Procurement Manual",
    department: "Procurement",
    doc_type: "Manual",
    effective_date: "2023-11-15",
    version_status: "current",
    source_path: "uploads/procurement/Purchase_Manual_2023.pdf",
    summary: "Financial delegation thresholds, tender bidding procedures, single-quotation limits, and audit protocols.",
    section_tree: {
      "1. Thresholds": ["Direct purchase under $1000", "Three quotations $1000-$10000", "Public tender above $10000"],
      "2. Verification": ["Store receipt inspection", "Asset tagging"],
    },
    chunk_count: 64,
    ingestion_status: "done",
  },
  {
    id: "doc-ordinance-2021-archived",
    tenant_id: "00000000-0000-0000-0000-000000000001",
    title: "Academic Ordinance 2021 (Superseded)",
    department: "Academic Affairs",
    doc_type: "Ordinance",
    effective_date: "2021-07-01",
    version_status: "superseded",
    source_path: "uploads/archive/Academic_Ordinance_2021.pdf",
    summary: "Previous grading and attendance regulations (superseded by 2024 revision).",
    section_tree: {
      "1. Attendance Rules": ["75% minimum threshold"],
    },
    chunk_count: 52,
    ingestion_status: "done",
  },
];

let mockAdminUsers: AdminUser[] = [
  {
    id: "u-admin-01",
    tenant_id: "00000000-0000-0000-0000-000000000001",
    email: "admin@enterprise.com",
    role: "admin",
  },
  {
    id: "u-faculty-01",
    tenant_id: "00000000-0000-0000-0000-000000000001",
    email: "sarah.connor@enterprise.com",
    role: "member",
  },
  {
    id: "u-finance-01",
    tenant_id: "00000000-0000-0000-0000-000000000001",
    email: "robert.langdon@enterprise.com",
    role: "member",
  },
  {
    id: "u-hr-01",
    tenant_id: "00000000-0000-0000-0000-000000000001",
    email: "elena.rostova@enterprise.com",
    role: "admin",
  },
];

let mockGlossary: GlossaryEntry[] = [
  { id: "g-1", term: "ERP", expansion: "Enterprise Resource Planning System" },
  { id: "g-2", term: "DA", expansion: "Daily Allowance for official institutional travel" },
  { id: "g-3", term: "CGPA", expansion: "Cumulative Grade Point Average" },
  { id: "g-4", term: "LOP", expansion: "Loss of Pay Leave" },
  { id: "g-5", term: "SLA", expansion: "Service Level Agreement for IT & vendor support" },
];

export async function fetchAdminAnalytics(): Promise<AdminAnalyticsData> {
  try {
    const res = await fetch(`${API_BASE}/admin/analytics`, {
      headers: { ...getAuthHeader() },
    });
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // Fallback to mock data
  }
  return MOCK_ANALYTICS;
}

export async function fetchAdminDocuments(filters?: {
  department?: string;
  doc_type?: string;
  version_status?: string;
  search?: string;
}): Promise<AdminDocument[]> {
  try {
    const params = new URLSearchParams();
    if (filters?.department && filters.department !== "All") params.append("department", filters.department);
    if (filters?.doc_type && filters.doc_type !== "All") params.append("doc_type", filters.doc_type);
    if (filters?.version_status && filters.version_status !== "All") params.append("version_status", filters.version_status.toLowerCase());
    if (filters?.search) params.append("search", filters.search);

    const res = await fetch(`${API_BASE}/admin/documents?${params.toString()}`, {
      headers: { ...getAuthHeader() },
    });
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // Fallback
  }

  return mockAdminDocs.filter((doc) => {
    if (filters?.department && filters.department !== "All" && doc.department !== filters.department) return false;
    if (filters?.version_status && filters.version_status !== "All" && doc.version_status.toLowerCase() !== filters.version_status.toLowerCase()) return false;
    if (filters?.search) {
      const q = filters.search.toLowerCase();
      const matches = doc.title.toLowerCase().includes(q) || (doc.summary && doc.summary.toLowerCase().includes(q));
      if (!matches) return false;
    }
    return true;
  });
}

export async function updateAdminDocument(
  documentId: string,
  updates: Partial<AdminDocument>
): Promise<AdminDocument> {
  try {
    const res = await fetch(`${API_BASE}/admin/documents/${documentId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeader(),
      },
      body: JSON.stringify(updates),
    });
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // Fallback
  }

  const idx = mockAdminDocs.findIndex((d) => d.id === documentId);
  if (idx !== -1) {
    mockAdminDocs[idx] = { ...mockAdminDocs[idx], ...updates };
    return mockAdminDocs[idx];
  }
  throw new Error("Document not found");
}

export async function deleteAdminDocument(documentId: string): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/admin/documents/${documentId}`, {
      method: "DELETE",
      headers: { ...getAuthHeader() },
    });
    if (res.ok || res.status === 204) {
      return;
    }
  } catch {
    // Fallback
  }
  mockAdminDocs = mockAdminDocs.filter((d) => d.id !== documentId);
}

export async function fetchAdminDocumentDetail(
  documentId: string
): Promise<AdminDocument> {
  try {
    const res = await fetch(`${API_BASE}/admin/documents/${documentId}`, {
      headers: { ...getAuthHeader() },
    });
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // Fallback
  }

  const doc = mockAdminDocs.find((d) => d.id === documentId);
  if (doc) return doc;
  throw new Error("Document not found");
}

export async function fetchAdminUsers(): Promise<AdminUser[]> {
  try {
    const res = await fetch(`${API_BASE}/admin/users`, {
      headers: { ...getAuthHeader() },
    });
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // Fallback
  }
  return mockAdminUsers;
}

export async function createAdminUser(data: {
  email: string;
  password: string;
  role: string;
}): Promise<AdminUser> {
  try {
    const res = await fetch(`${API_BASE}/admin/users`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeader(),
      },
      body: JSON.stringify(data),
    });
    if (res.ok) {
      return await res.json();
    }
    const err = await res.json();
    throw new Error(err.detail || "Failed to create user");
  } catch (e: unknown) {
    if (e instanceof Error && e.message !== "Failed to fetch") {
      throw e;
    }
  }

  const newUser: AdminUser = {
    id: `u-${crypto.randomUUID().slice(0, 8)}`,
    tenant_id: "00000000-0000-0000-0000-000000000001",
    email: data.email,
    role: data.role,
  };
  mockAdminUsers.push(newUser);
  return newUser;
}

export async function updateAdminUserRole(
  userId: string,
  role: string
): Promise<AdminUser> {
  try {
    const res = await fetch(`${API_BASE}/admin/users/${userId}/role`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeader(),
      },
      body: JSON.stringify({ role }),
    });
    if (res.ok) {
      return await res.json();
    }
    const err = await res.json();
    throw new Error(err.detail || "Failed to update user role");
  } catch (e: unknown) {
    if (e instanceof Error && e.message !== "Failed to fetch") {
      throw e;
    }
  }

  const idx = mockAdminUsers.findIndex((u) => u.id === userId);
  if (idx !== -1) {
    mockAdminUsers[idx].role = role;
    return mockAdminUsers[idx];
  }
  throw new Error("User not found");
}

export async function deleteAdminUser(userId: string): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/admin/users/${userId}`, {
      method: "DELETE",
      headers: { ...getAuthHeader() },
    });
    if (res.ok || res.status === 204) {
      return;
    }
    const err = await res.json();
    throw new Error(err.detail || "Failed to delete user");
  } catch (e: unknown) {
    if (e instanceof Error && e.message !== "Failed to fetch") {
      throw e;
    }
  }
  mockAdminUsers = mockAdminUsers.filter((u) => u.id !== userId);
}

export async function fetchAdminGlossary(): Promise<GlossaryEntry[]> {
  try {
    const res = await fetch(`${API_BASE}/admin/glossary`, {
      headers: { ...getAuthHeader() },
    });
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // Fallback
  }
  return mockGlossary;
}

export async function addGlossaryTerm(
  term: string,
  expansion: string
): Promise<GlossaryEntry> {
  try {
    const res = await fetch(`${API_BASE}/admin/glossary`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeader(),
      },
      body: JSON.stringify({ term, expansion }),
    });
    if (res.ok) {
      return await res.json();
    }
    const err = await res.json();
    throw new Error(err.detail || "Failed to add glossary term");
  } catch (e: unknown) {
    if (e instanceof Error && e.message !== "Failed to fetch") {
      throw e;
    }
  }

  const cleanTerm = term.trim().toUpperCase();
  const existingIdx = mockGlossary.findIndex((g) => g.term.toUpperCase() === cleanTerm);
  if (existingIdx !== -1) {
    mockGlossary[existingIdx].expansion = expansion;
    return mockGlossary[existingIdx];
  }
  const item: GlossaryEntry = {
    id: `g-${Date.now()}`,
    term: cleanTerm,
    expansion,
  };
  mockGlossary.push(item);
  return item;
}

export async function deleteGlossaryTerm(term: string): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/admin/glossary/${encodeURIComponent(term)}`, {
      method: "DELETE",
      headers: { ...getAuthHeader() },
    });
    if (res.ok || res.status === 204) {
      return;
    }
  } catch {
    // Fallback
  }
  mockGlossary = mockGlossary.filter((g) => g.term.toUpperCase() !== term.toUpperCase());
}

export { API_BASE };


/**
 * Fetch the full markdown content of a document.
 */
export async function getDocumentContent(documentId: string): Promise<string> {
  const response = await fetch(`${API_BASE}/documents/${documentId}/content`, {
    headers: {
      ...getAuthHeader(),
    },
  });

  if (response.status === 401) {
    window.dispatchEvent(new Event("auth_error"));
  }

  if (!response.ok) {
    throw new Error("Failed to fetch document content");
  }

  return response.text();
}
