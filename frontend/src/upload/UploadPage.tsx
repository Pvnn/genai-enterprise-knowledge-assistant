/**
 * Admin document upload page.
 * Owner: P7
 *
 * Shows a file picker (PDF only), department and doc_type text inputs,
 * and a status indicator that polls GET /documents/{document_id}/status
 * until ingestion_status reaches "done" or "failed".
 *
 * Only rendered for users with role === "admin"; non-admins are redirected
 * to the chat page.  Role check uses the CurrentUser returned by GET /auth/me
 * — no new auth logic added here.
 */
import React, { useCallback, useRef, useState } from "react";
import { API_BASE } from "../api/client";

type IngestionStatus = "idle" | "pending" | "processing" | "done" | "failed";

interface UploadResponse {
  document_id: string;
  ingestion_status: string;
}

interface StatusResponse {
  document_id: string;
  ingestion_status: string;
  detail?: string;
}

const POLL_INTERVAL_MS = 3000;

const UploadPage: React.FC = () => {
  const fileRef = useRef<HTMLInputElement>(null);
  const [department, setDepartment] = useState("");
  const [docType, setDocType] = useState("");
  const [status, setStatus] = useState<IngestionStatus>("idle");
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const pollStatus = useCallback((docId: string, token: string) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/documents/${docId}/status`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          clearInterval(interval);
          setStatus("failed");
          setErrorMsg(`Status check failed: ${res.status}`);
          return;
        }
        const data: StatusResponse = await res.json();
        if (data.ingestion_status === "done" || data.ingestion_status === "failed") {
          clearInterval(interval);
          setStatus(data.ingestion_status as IngestionStatus);
          if (data.ingestion_status === "failed") {
            setErrorMsg(data.detail ?? "Ingestion failed.");
          }
        } else {
          setStatus(data.ingestion_status as IngestionStatus);
        }
      } catch {
        clearInterval(interval);
        setStatus("failed");
        setErrorMsg("Network error while polling status.");
      }
    }, POLL_INTERVAL_MS);
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setErrorMsg(null);

      const file = fileRef.current?.files?.[0];
      if (!file) { setErrorMsg("Please select a PDF file."); return; }
      if (!department.trim()) { setErrorMsg("Department is required."); return; }
      if (!docType.trim()) { setErrorMsg("Document type is required."); return; }

      // TODO P7: retrieve token from your auth store/context
      const token = localStorage.getItem("access_token") ?? "";

      const form = new FormData();
      form.append("file", file);
      form.append("department", department.trim());
      form.append("doc_type", docType.trim());

      setStatus("pending");

      try {
        const res = await fetch(`${API_BASE}/documents/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        });

        if (res.status === 403) {
          setStatus("failed");
          setErrorMsg("Only admin users can upload documents.");
          return;
        }
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          setStatus("failed");
          setErrorMsg(err.detail ?? `Upload failed (${res.status}).`);
          return;
        }

        const data: UploadResponse = await res.json();
        setDocumentId(data.document_id);
        setStatus("processing");
        pollStatus(data.document_id, token);
      } catch {
        setStatus("failed");
        setErrorMsg("Network error during upload.");
      }
    },
    [department, docType, pollStatus]
  );

  return (
    <div style={{ maxWidth: 480, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>Upload Document</h1>
      <p style={{ color: "#666", fontSize: 14 }}>
        Admin only. PDF files only. Ingestion runs in the background.
      </p>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <label>
          PDF File
          <input ref={fileRef} type="file" accept=".pdf" style={{ display: "block", marginTop: 4 }} />
        </label>

        <label>
          Department
          <input
            type="text"
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            placeholder="e.g. HR"
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>

        <label>
          Document Type
          <input
            type="text"
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            placeholder="e.g. policy"
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>

        <button type="submit" disabled={status === "pending" || status === "processing"}>
          {status === "pending" || status === "processing" ? "Uploading…" : "Upload"}
        </button>
      </form>

      {status !== "idle" && (
        <div style={{ marginTop: 16 }}>
          <strong>Status:</strong>{" "}
          <span
            style={{
              color:
                status === "done" ? "green" :
                status === "failed" ? "red" :
                "#b07800",
            }}
          >
            {status}
          </span>
          {documentId && (
            <div style={{ fontSize: 12, color: "#888", marginTop: 4 }}>
              Document ID: {documentId}
            </div>
          )}
          {errorMsg && (
            <div style={{ color: "red", marginTop: 8, fontSize: 13 }}>{errorMsg}</div>
          )}
        </div>
      )}
    </div>
  );
};

export default UploadPage;