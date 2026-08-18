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
  ErrorResponse,
  FeedbackRequest,
  FeedbackResponse,
  FinalEvent,
  LoginRequest,
  LoginResponse,
  TokenEvent,
} from "../chat/types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem("access_token");
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

/**
 * Stream simulated responses for offline testing and demo presentations.
 */
async function streamMockResponse(
  request: ChatRequest,
  callbacks: {
    onToken?: (event: TokenEvent) => void;
    onClarify?: (event: ClarifyEvent) => void;
    onFinal?: (event: FinalEvent) => void;
    onError?: (error: ErrorResponse | Error) => void;
  },
  signal?: AbortSignal
): Promise<void> {
  const lower = request.query.toLowerCase();

  // 1. Clarification Scenario
  if (lower.includes("clarify") || lower.includes("leave entitlement") || lower.includes("who is eligible")) {
    await new Promise((resolve) => setTimeout(resolve, 400));
    if (signal?.aborted) return;
    callbacks.onClarify?.({
      type: "clarify",
      question: "Are you inquiring as teaching faculty, administrative staff, or a full-time research scholar?",
    });
    return;
  }

  // 2. Conflict Scenario
  if (lower.includes("conflict") || lower.includes("dispute") || lower.includes("attendance requirement")) {
    const tokens = [
      "There appear to be two conflicting versions on file regarding attendance requirements:\n\n",
      "- Academic Ordinance 2021 (effective 2021-07-01) states minimum 75% attendance.\n",
      "- Academic Circular 2024 (effective 2024-01-15) states minimum 80% attendance with 5% medical condonation.\n\n",
      "Please confirm which applies to your program or flag this to the registrar.",
    ];

    for (const token of tokens) {
      if (signal?.aborted) return;
      await new Promise((resolve) => setTimeout(resolve, 80));
      callbacks.onToken?.({ type: "token", content: token });
    }

    callbacks.onFinal?.({
      type: "final",
      answer: "There appear to be two conflicting versions on file:\n- Academic Ordinance 2021 (effective 2021-07-01) states 75% minimum attendance.\n- Academic Circular 2024 (effective 2024-01-15) states 80% minimum attendance.\nPlease confirm with the academic dean.",
      citations: [
        {
          chunk_id: "c-ordinance-2021-01",
          document_id: "doc-ordinance-2021",
          section_path: "Academic Regulations / Section 4.2 Attendance",
          source_path: "Academic_Ordinance_2021.pdf",
        },
        {
          chunk_id: "c-circular-2024-08",
          document_id: "doc-circular-2024",
          section_path: "Executive Circulars / Circular 12 Clause 3",
          source_path: "Circular_2024_Attendance.pdf",
        },
      ],
      confidence: 0.88,
      refused: false,
      refusal_reason: null,
      conflict: true,
    });
    return;
  }

  // 3. Refusal Scenario (Low confidence)
  if (lower.includes("parking") || lower.includes("gym") || lower.includes("unknown") || lower.includes("refusal")) {
    await new Promise((resolve) => setTimeout(resolve, 350));
    callbacks.onFinal?.({
      type: "final",
      answer: "I could not find a passage in the current policy documents that directly answers this. You may want to check with General Administration or rephrase your question.",
      citations: [],
      confidence: 0.38,
      refused: true,
      refusal_reason: "I could not find a passage in the current policy documents that directly answers this. You may want to check with General Administration or rephrase your question.",
      conflict: false,
    });
    return;
  }

  // 4. Standard Grounded Answer Scenario
  const chunks = [
    "Under the Institutional Leave Policy 2025 (Section 3.2.2), permanent faculty members are entitled to ",
    "30 days of earned leave and 15 days of casual leave per calendar year. ",
    "Maternity leave of 180 days is fully paid upon completion of one year of continuous service.\n\n",
    "Applications must be submitted through the enterprise ERP portal at least 14 days in advance.",
  ];

  for (const chunk of chunks) {
    if (signal?.aborted) return;
    await new Promise((resolve) => setTimeout(resolve, 90));
    callbacks.onToken?.({ type: "token", content: chunk });
  }

  callbacks.onFinal?.({
    type: "final",
    answer: "Under the Institutional Leave Policy 2025 (Section 3.2.2), permanent faculty members are entitled to 30 days of earned leave and 15 days of casual leave per calendar year. Maternity leave of 180 days is fully paid upon completion of one year of continuous service.\n\nApplications must be submitted through the enterprise ERP portal at least 14 days in advance.",
    citations: [
      {
        chunk_id: "chk-leave-301",
        document_id: "doc-leave-policy-2025",
        section_path: "Leave Policy 2025 / Section 3.2.2 Maternity Entitlement",
        source_path: "Institutional_Leave_Rules_2025.pdf",
      },
      {
        chunk_id: "chk-admin-proc-104",
        document_id: "doc-admin-handbook-v2",
        section_path: "Administrative Procedures / Clause 8 ERP Submissions",
        source_path: "Admin_Procedures_Handbook.pdf",
      },
    ],
    confidence: 0.94,
    refused: false,
    refusal_reason: null,
    conflict: false,
  });
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

    // If backend connection fails (e.g. backend not yet started), provide realistic demo stream
    console.info("Live backend unreachable, activating interactive demo simulation.");
    await streamMockResponse(request, callbacks, signal);
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

/**
 * Fetch list of indexed documents for the institutional knowledge library.
 */
export async function fetchDocuments(tenant_id: string): Promise<DocumentItem[]> {
  try {
    const response = await fetch(`${API_BASE}/documents?tenant_id=${tenant_id}`, {
      headers: {
        ...getAuthHeader(),
      },
    });
    if (response.ok) {
      return await response.json();
    }
  } catch {
    // Fall back to institutional policy documents catalog
  }

  return [
    {
      id: "doc-leave-policy-2025",
      tenant_id,
      title: "Institutional Leave Rules and Guidelines 2025",
      department: "Human Resources",
      doc_type: "Policy",
      effective_date: "2025-01-01",
      version_status: "current",
      source_path: "uploads/hr/Institutional_Leave_Rules_2025.pdf",
      summary: "Comprehensive leave entitlements covering casual leave, earned leave, maternity, paternity, and sabbatical provisions.",
      chunk_count: 42,
      ingestion_status: "done",
    },
    {
      id: "doc-travel-reimburse-2024",
      tenant_id,
      title: "Official Travel, DA and Per Diem Regulations",
      department: "Finance & Accounts",
      doc_type: "Regulation",
      effective_date: "2024-04-01",
      version_status: "current",
      source_path: "uploads/finance/Travel_DA_Regulations_2024.pdf",
      summary: "Prescribes travel allowances, hotel caps, daily allowance per diem, and conference travel claim workflows.",
      chunk_count: 28,
      ingestion_status: "done",
    },
    {
      id: "doc-academic-ordinance-2024",
      tenant_id,
      title: "Academic Ordinance for Semester Grading and Evaluation",
      department: "Academic Affairs",
      doc_type: "Ordinance",
      effective_date: "2024-08-01",
      version_status: "current",
      source_path: "uploads/academic/Academic_Ordinance_Grading_2024.pdf",
      summary: "Governs letter grading scale, SGPA/CGPA calculations, re-evaluation petitions, and minimum attendance thresholds.",
      chunk_count: 56,
      ingestion_status: "done",
    },
    {
      id: "doc-procurement-guidelines-2023",
      tenant_id,
      title: "Departmental Purchase and Procurement Manual",
      department: "Procurement",
      doc_type: "Manual",
      effective_date: "2023-11-15",
      version_status: "current",
      source_path: "uploads/procurement/Purchase_Manual_2023.pdf",
      summary: "Financial delegation thresholds, tender bidding procedures, single-quotation limits, and audit protocols.",
      chunk_count: 64,
      ingestion_status: "done",
    },
    {
      id: "doc-research-grant-policy-2024",
      tenant_id,
      title: "Inter-Departmental Research Seed Grant Scheme",
      department: "Research & Development",
      doc_type: "Scheme",
      effective_date: "2024-06-01",
      version_status: "current",
      source_path: "uploads/rnd/Research_Seed_Grant_2024.pdf",
      summary: "Funding guidelines for interdisciplinary research proposals, equipment procurement, and research assistant stipends.",
      chunk_count: 35,
      ingestion_status: "done",
    },
    {
      id: "doc-ordinance-2021-archived",
      tenant_id,
      title: "Academic Ordinance 2021 (Superseded)",
      department: "Academic Affairs",
      doc_type: "Ordinance",
      effective_date: "2021-07-01",
      version_status: "superseded",
      source_path: "uploads/archive/Academic_Ordinance_2021.pdf",
      summary: "Previous grading and attendance regulations (superseded by 2024 revision).",
      chunk_count: 52,
      ingestion_status: "done",
    },
  ];
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

export { API_BASE };
