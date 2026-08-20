/**
 * UploadModal Component.
 * Owner: P7
 *
 * Glassmorphic modal overlay for admin document ingestion.
 * Supports PDF file selection / drag-and-drop, department/doc_type metadata,
 * and live ingestion status polling until completion.
 */

import React, { useState, useRef, useCallback } from "react";
import {
  X,
  UploadSimple,
  FilePdf,
  CheckCircle,
  WarningCircle,
  SpinnerGap,
  Buildings,
  Tag,
  ArrowClockwise,
} from "@phosphor-icons/react";
import { uploadDocument, getDocumentStatus } from "../api/client";
import { DocumentStatusResponse, UploadResponse } from "../chat/types";

export type IngestionStatus = "idle" | "pending" | "processing" | "done" | "failed";

const POLL_INTERVAL_MS = 2500;

export interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess?: (documentId: string) => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
}) => {
  const fileRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [department, setDepartment] = useState("");
  const [docType, setDocType] = useState("");
  const [status, setStatus] = useState<IngestionStatus>("idle");
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const resetForm = () => {
    setSelectedFile(null);
    setDepartment("");
    setDocType("");
    setStatus("idle");
    setDocumentId(null);
    setErrorMsg(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const handleModalClose = () => {
    resetForm();
    onClose();
  };

  const pollStatus = useCallback(
    (docId: string) => {
      const interval = setInterval(async () => {
        try {
          const data: DocumentStatusResponse = await getDocumentStatus(docId);
          if (data.ingestion_status === "done" || data.ingestion_status === "failed") {
            clearInterval(interval);
            setStatus(data.ingestion_status as IngestionStatus);
            if (data.ingestion_status === "failed") {
              setErrorMsg(data.detail ?? "Ingestion failed.");
            } else if (data.ingestion_status === "done") {
              onUploadSuccess?.(docId);
            }
          } else {
            setStatus(data.ingestion_status as IngestionStatus);
          }
        } catch (err: unknown) {
          clearInterval(interval);
          setStatus("failed");
          setErrorMsg(err instanceof Error ? err.message : "Status check failed.");
        }
      }, POLL_INTERVAL_MS);
    },
    [onUploadSuccess]
  );

  const handleFileChange = (file: File | undefined) => {
    if (!file) return;
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setErrorMsg("Only PDF files are supported.");
      return;
    }
    setErrorMsg(null);
    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setErrorMsg(null);

      const file = selectedFile || fileRef.current?.files?.[0];
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
    [selectedFile, department, docType, pollStatus]
  );

  if (!isOpen) return null;

  const quickDepts = ["Human Resources", "Academic Affairs", "Finance & Accounts", "Procurement"];
  const quickDocTypes = ["Policy", "Circular", "Ordinance", "Manual", "Syllabus"];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="w-full max-w-lg rounded-2xl border border-hairline bg-surface p-6 shadow-2xl space-y-5 text-ink animate-in fade-in zoom-in-95 duration-150 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-hairline">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-primary-brand/10 border border-primary-brand/20 flex items-center justify-center text-primary-brand">
              <UploadSimple size={18} weight="bold" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-ink tracking-tight">
                  Upload Document
                </h2>
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-primary-brand/10 text-primary-brand border border-primary-brand/20">
                  Admin
                </span>
              </div>
              <p className="text-xs text-ink-muted">
                Admin only. PDF files only. Ingestion runs in the background.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleModalClose}
            className="p-1.5 rounded-xl text-ink-muted hover:text-ink hover:bg-surface-muted transition-colors cursor-pointer"
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Error Alert */}
        {errorMsg && (
          <div className="flex items-start gap-2.5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-700 dark:text-rose-300">
            <WarningCircle size={16} className="mt-0.5 shrink-0" weight="fill" />
            <p className="leading-snug">{errorMsg}</p>
          </div>
        )}

        {/* Status Indicator Banner */}
        {status !== "idle" && (
          <div
            className={`p-4 rounded-xl border flex flex-col gap-2 ${
              status === "done"
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-800 dark:text-emerald-200"
                : status === "failed"
                ? "bg-rose-500/10 border-rose-500/30 text-rose-800 dark:text-rose-200"
                : "bg-primary-brand/10 border-primary-brand/30 text-primary-brand"
            }`}
          >
            <div className="flex items-center justify-between text-xs font-semibold">
              <div className="flex items-center gap-2">
                {status === "done" ? (
                  <CheckCircle size={18} weight="fill" className="text-emerald-500" />
                ) : status === "failed" ? (
                  <WarningCircle size={18} weight="fill" className="text-rose-500" />
                ) : (
                  <SpinnerGap size={18} className="animate-spin text-primary-brand" />
                )}
                <span className="capitalize">Status: {status}</span>
              </div>
              {status === "processing" && (
                <span className="text-[11px] font-normal text-ink-muted animate-pulse">
                  Chunking & Indexing Embeddings…
                </span>
              )}
            </div>

            {documentId && (
              <div className="text-[11px] font-mono text-ink-muted bg-surface/50 px-2.5 py-1 rounded-lg border border-hairline w-fit">
                Document ID: {documentId}
              </div>
            )}
          </div>
        )}

        {status === "done" ? (
          <div className="py-4 text-center space-y-4">
            <p className="text-xs text-ink-muted">
              The institutional document has been chunked, embedded, and added to the knowledge index.
            </p>
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                type="button"
                onClick={resetForm}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-xl border border-hairline bg-surface hover:bg-surface-muted text-ink transition-colors cursor-pointer"
              >
                <ArrowClockwise size={14} />
                <span>Upload Another</span>
              </button>
              <button
                type="button"
                onClick={handleModalClose}
                className="px-5 py-2 text-xs font-medium rounded-xl bg-primary-brand text-white hover:opacity-90 transition-opacity cursor-pointer shadow-xs"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} noValidate className="space-y-4 text-xs">
            {/* PDF File Drag & Drop Zone */}
            <div>
              <label htmlFor="pdf-upload-input" className="block font-medium text-ink-muted mb-1.5">
                PDF File
              </label>
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
                className={`relative flex flex-col items-center justify-center p-5 rounded-2xl border-2 border-dashed transition-all cursor-pointer ${
                  isDragging
                    ? "border-primary-brand bg-primary-brand/5 scale-[1.01]"
                    : selectedFile
                    ? "border-emerald-500/50 bg-emerald-500/5"
                    : "border-hairline bg-surface hover:border-primary-brand/50 hover:bg-surface-muted/50"
                }`}
              >
                <input
                  id="pdf-upload-input"
                  ref={fileRef}
                  type="file"
                  accept=".pdf,application/pdf"
                  aria-label="PDF File"
                  onChange={(e) => handleFileChange(e.target.files?.[0])}
                  disabled={status === "pending" || status === "processing"}
                  className="sr-only"
                />

                {selectedFile ? (
                  <div className="flex items-center gap-3 w-full">
                    <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-600 dark:text-red-400 shrink-0">
                      <FilePdf size={22} weight="fill" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-bold text-ink truncate">{selectedFile.name}</p>
                      <p className="text-[11px] text-ink-muted">
                        {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • PDF Document
                      </p>
                    </div>
                    <span className="text-[11px] text-primary-brand hover:underline font-medium">
                      Change
                    </span>
                  </div>
                ) : (
                  <div className="text-center space-y-1.5">
                    <div className="w-10 h-10 mx-auto rounded-xl bg-surface-muted border border-hairline flex items-center justify-center text-ink-muted">
                      <FilePdf size={22} />
                    </div>
                    <p className="text-xs font-semibold text-ink">
                      Click to choose file or drag & drop PDF
                    </p>
                    <p className="text-[10px] text-ink-muted">Institutional policies, circulars, or regulations (max 50MB)</p>
                  </div>
                )}
              </div>
            </div>

            {/* Department Field */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="dept-input" className="font-medium text-ink-muted flex items-center gap-1.5">
                  <Buildings size={14} />
                  <span>Department</span>
                </label>
              </div>
              <input
                id="dept-input"
                type="text"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                placeholder="e.g. Human Resources"
                disabled={status === "pending" || status === "processing"}
                className="w-full px-3 py-2 text-xs rounded-xl border border-hairline bg-surface text-ink placeholder-ink-muted focus:outline-none focus:ring-2 focus:ring-primary-brand/30 shadow-2xs"
              />
              <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                {quickDepts.map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setDepartment(d)}
                    className="text-[10px] px-2 py-0.5 rounded-lg border border-hairline bg-surface hover:bg-surface-muted text-ink-muted transition-colors cursor-pointer"
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>

            {/* Document Type Field */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="doctype-input" className="font-medium text-ink-muted flex items-center gap-1.5">
                  <Tag size={14} />
                  <span>Document Type</span>
                </label>
              </div>
              <input
                id="doctype-input"
                type="text"
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
                placeholder="e.g. Policy"
                disabled={status === "pending" || status === "processing"}
                className="w-full px-3 py-2 text-xs rounded-xl border border-hairline bg-surface text-ink placeholder-ink-muted focus:outline-none focus:ring-2 focus:ring-primary-brand/30 shadow-2xs"
              />
              <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                {quickDocTypes.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setDocType(t)}
                    className="text-[10px] px-2 py-0.5 rounded-lg border border-hairline bg-surface hover:bg-surface-muted text-ink-muted transition-colors cursor-pointer"
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-hairline">
              <button
                type="button"
                onClick={handleModalClose}
                disabled={status === "pending" || status === "processing"}
                className="px-4 py-2 rounded-xl border border-hairline text-ink-muted hover:bg-surface-muted transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={status === "pending" || status === "processing"}
                className="flex items-center gap-1.5 px-5 py-2 rounded-xl bg-primary-brand hover:opacity-90 text-white font-medium transition-all disabled:opacity-50 cursor-pointer shadow-xs active:scale-95"
              >
                {status === "pending" || status === "processing" ? (
                  <>
                    <SpinnerGap size={14} className="animate-spin" />
                    <span>Uploading…</span>
                  </>
                ) : (
                  <>
                    <UploadSimple size={14} weight="bold" />
                    <span>Upload</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default UploadModal;
