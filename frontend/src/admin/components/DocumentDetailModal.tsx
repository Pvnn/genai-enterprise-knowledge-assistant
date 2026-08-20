/**
 * DocumentDetailModal Component.
 * Allows administrators to inspect document summaries, section trees, and metadata.
 */

import React, { useState } from "react";
import {
  X,
  FileText,
  TreeStructure,
  Info,
  Calendar,
  Building,
  Tag,
  Hash,
  CheckCircle,
  WarningCircle,
  Clock,
} from "@phosphor-icons/react";
import { AdminDocument } from "../types";

interface DocumentDetailModalProps {
  document: AdminDocument | null;
  onClose: () => void;
}

export const DocumentDetailModal: React.FC<DocumentDetailModalProps> = ({
  document,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<"summary" | "tree" | "metadata">("summary");

  if (!document) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="w-full max-w-2xl bg-surface border border-hairline rounded-3xl shadow-xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-5 border-b border-hairline flex items-start justify-between gap-4 bg-surface-muted/30">
          <div className="flex items-start gap-3 min-w-0">
            <div className="w-10 h-10 rounded-2xl bg-primary-brand/10 text-primary-brand flex items-center justify-center shrink-0 mt-0.5">
              <FileText size={22} weight="bold" />
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-bold text-ink truncate" title={document.title}>
                {document.title}
              </h3>
              <div className="flex flex-wrap items-center gap-2 mt-1">
                {document.department && (
                  <span className="text-[11px] px-2 py-0.5 rounded-lg bg-surface border border-hairline text-ink-muted">
                    {document.department}
                  </span>
                )}
                {document.doc_type && (
                  <span className="text-[11px] px-2 py-0.5 rounded-lg bg-surface border border-hairline text-ink-muted">
                    {document.doc_type}
                  </span>
                )}
                <span
                  className={`text-[11px] font-semibold px-2 py-0.5 rounded-lg ${
                    document.version_status === "current"
                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                      : "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                  }`}
                >
                  {document.version_status === "current" ? "Active Policy" : "Superseded"}
                </span>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-xl text-ink-muted hover:text-ink hover:bg-surface-muted transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Navigation Sub-Tabs */}
        <div className="flex items-center gap-2 px-5 pt-3 border-b border-hairline text-xs font-medium">
          <button
            type="button"
            onClick={() => setActiveTab("summary")}
            className={`pb-2.5 px-2 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "summary"
                ? "border-primary-brand text-primary-brand font-semibold"
                : "border-transparent text-ink-muted hover:text-ink"
            }`}
          >
            <Info size={14} />
            <span>Summary & Insights</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("tree")}
            className={`pb-2.5 px-2 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "tree"
                ? "border-primary-brand text-primary-brand font-semibold"
                : "border-transparent text-ink-muted hover:text-ink"
            }`}
          >
            <TreeStructure size={14} />
            <span>Section Hierarchy</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("metadata")}
            className={`pb-2.5 px-2 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === "metadata"
                ? "border-primary-brand text-primary-brand font-semibold"
                : "border-transparent text-ink-muted hover:text-ink"
            }`}
          >
            <Tag size={14} />
            <span>Ingestion Metadata</span>
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 overflow-y-auto flex-1 space-y-4 text-xs">
          {activeTab === "summary" && (
            <div className="space-y-4">
              <div>
                <h4 className="font-semibold text-ink mb-1.5">Executive Summary</h4>
                <div className="p-4 rounded-2xl bg-surface-muted/50 border border-hairline leading-relaxed text-ink/90">
                  {document.summary || "No automated summary available for this document."}
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                <div className="p-3 rounded-xl bg-surface-muted/30 border border-hairline">
                  <span className="text-[11px] text-ink-muted block">Indexed Chunks</span>
                  <span className="text-base font-bold text-ink">{document.chunk_count}</span>
                </div>
                <div className="p-3 rounded-xl bg-surface-muted/30 border border-hairline">
                  <span className="text-[11px] text-ink-muted block">Effective Date</span>
                  <span className="text-xs font-mono font-bold text-ink">
                    {document.effective_date || "Not set"}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-surface-muted/30 border border-hairline">
                  <span className="text-[11px] text-ink-muted block">Ingestion State</span>
                  <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 capitalize">
                    {document.ingestion_status}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-surface-muted/30 border border-hairline">
                  <span className="text-[11px] text-ink-muted block">Version Type</span>
                  <span className="text-xs font-bold text-ink capitalize">
                    {document.version_status}
                  </span>
                </div>
              </div>
            </div>
          )}

          {activeTab === "tree" && (
            <div className="space-y-3">
              <h4 className="font-semibold text-ink">Extracted Document Structure</h4>
              {document.section_tree && Object.keys(document.section_tree).length > 0 ? (
                <div className="p-4 rounded-2xl bg-surface-muted/40 border border-hairline font-mono text-[11px] space-y-3">
                  {Array.isArray(document.section_tree) ? (
                    document.section_tree.map((node, i) => (
                      <div key={i} className="pl-2 border-l-2 border-primary-brand/30">
                        {typeof node === "string" ? node : JSON.stringify(node)}
                      </div>
                    ))
                  ) : (
                    Object.entries(document.section_tree).map(([section, items]) => (
                      <div key={section} className="space-y-1">
                        <div className="font-bold text-primary-brand flex items-center gap-1.5">
                          <TreeStructure size={13} />
                          <span>{section}</span>
                        </div>
                        {Array.isArray(items) && (
                          <div className="pl-4 space-y-1 border-l border-hairline text-ink-muted">
                            {items.map((item, j) => (
                              <div key={j}>• {typeof item === "string" ? item : JSON.stringify(item)}</div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              ) : (
                <div className="p-6 text-center text-ink-muted rounded-2xl bg-surface-muted/30 border border-hairline">
                  No section hierarchy extracted for this document.
                </div>
              )}
            </div>
          )}

          {activeTab === "metadata" && (
            <div className="space-y-3">
              <div className="space-y-2">
                <div className="flex justify-between py-2 border-b border-hairline">
                  <span className="text-ink-muted">Document UUID</span>
                  <span className="font-mono text-ink select-all">{document.id}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-hairline">
                  <span className="text-ink-muted">Tenant UUID</span>
                  <span className="font-mono text-ink select-all">{document.tenant_id}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-hairline">
                  <span className="text-ink-muted">Storage Source Path</span>
                  <span className="font-mono text-ink truncate max-w-xs">{document.source_path || "—"}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-hairline">
                  <span className="text-ink-muted">Department</span>
                  <span className="text-ink">{document.department || "General"}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-hairline">
                  <span className="text-ink-muted">Document Classification</span>
                  <span className="text-ink">{document.doc_type || "Standard"}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-hairline flex justify-end bg-surface-muted/20">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium rounded-xl bg-surface border border-hairline text-ink hover:bg-surface-muted transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default DocumentDetailModal;
