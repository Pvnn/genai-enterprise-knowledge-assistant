/**
 * Admin document upload page.
 * Owner: P7
 *
 * Shows a file picker (PDF only), department and doc_type text inputs,
 * and a status indicator that polls GET /documents/{document_id}/status
 * until ingestion_status reaches "done" or "failed".
 *
 * Only rendered for users with role === "admin"; non-admins are redirected
 * to the chat page.
 */
import React, { useCallback, useRef, useState } from "react";
import { uploadDocument, getDocumentStatus } from "../api/client";
import { DocumentStatusResponse, UploadResponse } from "../chat/types";

type IngestionStatus = "idle" | "pending" | "processing" | "done" | "failed";

const POLL_INTERVAL_MS = 3000;

interface UploadPageProps {
  onNavigateBack?: () => void;
}

const UploadPage: React.FC<UploadPageProps> = ({ onNavigateBack }) => {
  const fileRef = useRef<HTMLInputElement>(null);
  const [department, setDepartment] = useState("");
  const [docType, setDocType] = useState("");
  const [status, setStatus] = useState<IngestionStatus>("idle");
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleBack = () => {
    if (onNavigateBack) {
      onNavigateBack();
    } else {
      window.history.pushState({}, "", "/chat");
      window.dispatchEvent(new PopStateEvent("popstate"));
    }
  };

  const pollStatus = useCallback((docId: string) => {
    const interval = setInterval(async () => {
      try {
        const data: DocumentStatusResponse = await getDocumentStatus(docId);
        if (data.ingestion_status === "done" || data.ingestion_status === "failed") {
          clearInterval(interval);
          setStatus(data.ingestion_status as IngestionStatus);
          if (data.ingestion_status === "failed") {
            setErrorMsg(data.detail ?? "Ingestion failed.");
          }
        } else {
          setStatus(data.ingestion_status as IngestionStatus);
        }
      } catch (err: unknown) {
        clearInterval(interval);
        setStatus("failed");
        setErrorMsg(
          err instanceof Error ? err.message : "Status check failed."
        );
      }
    }, POLL_INTERVAL_MS);
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setErrorMsg(null);

      const file = fileRef.current?.files?.[0];
      if (!file) {
        setErrorMsg("Please select a PDF file.");
        return;
      }
      if (!department.trim()) {
        setErrorMsg("Department is required.");
        return;
      }
      if (!docType.trim()) {
        setErrorMsg("Document type is required.");
        return;
      }

      setStatus("pending");

      try {
        const data: UploadResponse = await uploadDocument(
          file,
          department.trim(),
          docType.trim()
        );
        setDocumentId(data.document_id);
        setStatus("processing");
        pollStatus(data.document_id);
      } catch (err: unknown) {
        setStatus("failed");
        setErrorMsg(err instanceof Error ? err.message : "Upload failed.");
      }
    },
    [department, docType, pollStatus]
  );

  return (
    <div style={{ maxWidth: 480, margin: "2rem auto", fontFamily: "sans-serif", padding: "0 1rem" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
        <h1>Upload Document</h1>
        <button
          type="button"
          onClick={handleBack}
          style={{
            padding: "6px 12px",
            fontSize: 12,
            borderRadius: 8,
            border: "1px solid #ccc",
            background: "transparent",
            cursor: "pointer",
          }}
        >
          &larr; Back to Workspace
        </button>
      </div>

      <p style={{ color: "#666", fontSize: 14, marginBottom: "1.5rem" }}>
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
            placeholder="e.g. Human Resources"
            style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px", boxSizing: "border-box" }}
          />
        </label>

        <label>
          Document Type
          <input
            type="text"
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            placeholder="e.g. Policy"
            style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px", boxSizing: "border-box" }}
          />
        </label>

        <button
          type="submit"
          disabled={status === "pending" || status === "processing"}
          style={{
            marginTop: 8,
            padding: "8px 16px",
            backgroundColor: "#2563eb",
            color: "white",
            border: "none",
            borderRadius: 6,
            cursor: status === "pending" || status === "processing" ? "not-allowed" : "pointer",
          }}
        >
          {status === "pending" || status === "processing" ? "Uploading…" : "Upload"}
        </button>
      </form>

      {(status !== "idle" || errorMsg) && (
        <div style={{ marginTop: 16, padding: "12px", borderRadius: 8, backgroundColor: "#f8fafc", border: "1px solid #e2e8f0" }}>
          {status !== "idle" && (
            <div>
              <strong>Status:</strong>{" "}
              <span
                style={{
                  color:
                    status === "done" ? "#16a34a" :
                    status === "failed" ? "#dc2626" :
                    "#b45309",
                  fontWeight: 600,
                }}
              >
                {status}
              </span>
            </div>
          )}
          {documentId && (
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
              Document ID: {documentId}
            </div>
          )}
          {errorMsg && (
            <div style={{ color: "#dc2626", marginTop: status !== "idle" ? 8 : 0, fontSize: 13 }}>{errorMsg}</div>
          )}
        </div>
      )}
    </div>
  );
};

export default UploadPage;