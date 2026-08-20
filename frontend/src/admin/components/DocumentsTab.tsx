/**
 * DocumentsTab Component for Admin Dashboard.
 * Full document catalog management: search, filter, metadata edit, version status toggle, inspect, and delete.
 */

import React, { useState } from "react";
import {
  FileText,
  MagnifyingGlass,
  Funnel,
  Plus,
  Trash,
  Eye,
  CheckCircle,
  ClockCounterClockwise,
  WarningCircle,
  CircleNotch,
  ArrowClockwise,
  Tag,
  ArrowsLeftRight,
} from "@phosphor-icons/react";
import { AdminDocument } from "../types";
import { DocumentDetailModal } from "./DocumentDetailModal";
import { UploadModal } from "./UploadModal";

interface DocumentsTabProps {
  documents: AdminDocument[];
  loading: boolean;
  onRefresh: () => void;
  onUpdateDocument: (docId: string, updates: Partial<AdminDocument>) => Promise<void>;
  onDeleteDocument: (docId: string) => Promise<void>;
}

export const DocumentsTab: React.FC<DocumentsTabProps> = ({
  documents,
  loading,
  onRefresh,
  onUpdateDocument,
  onDeleteDocument,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDept, setSelectedDept] = useState("All");
  const [selectedVersion, setSelectedVersion] = useState("All");
  const [selectedDocForDetail, setSelectedDocForDetail] = useState<AdminDocument | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [deletingDocId, setDeletingDocId] = useState<string | null>(null);
  const [confirmDeleteDoc, setConfirmDeleteDoc] = useState<AdminDocument | null>(null);

  const departments = [
    "All",
    "Human Resources",
    "Finance & Accounts",
    "Academic Affairs",
    "Procurement",
    "Research & Development",
  ];

  const filteredDocs = documents.filter((doc) => {
    const matchesSearch =
      doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (doc.department && doc.department.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (doc.summary && doc.summary.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesDept = selectedDept === "All" || doc.department === selectedDept;
    const matchesVersion =
      selectedVersion === "All" ||
      (selectedVersion === "Active" && doc.version_status === "current") ||
      (selectedVersion === "Superseded" && doc.version_status === "superseded");

    return matchesSearch && matchesDept && matchesVersion;
  });

  const handleToggleVersion = async (doc: AdminDocument) => {
    const nextStatus = doc.version_status === "current" ? "superseded" : "current";
    await onUpdateDocument(doc.id, { version_status: nextStatus });
  };

  const handleDeleteConfirm = async () => {
    if (!confirmDeleteDoc) return;
    setDeletingDocId(confirmDeleteDoc.id);
    try {
      await onDeleteDocument(confirmDeleteDoc.id);
    } finally {
      setDeletingDocId(null);
      setConfirmDeleteDoc(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Bar: Search, Filters, and Upload Action */}
      <div className="p-5 rounded-2xl bg-surface border border-hairline shadow-2xs flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <MagnifyingGlass
            size={16}
            className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-muted"
          />
          <input
            type="text"
            placeholder="Search policies, departments, summaries..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-xs rounded-xl bg-surface-muted border border-hairline text-ink placeholder:text-ink-muted focus:outline-none focus:border-primary-brand"
          />
        </div>

        {/* Filters and Actions */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Department Filter */}
          <select
            value={selectedDept}
            onChange={(e) => setSelectedDept(e.target.value)}
            className="py-2 px-3 text-xs rounded-xl bg-surface-muted border border-hairline text-ink focus:outline-none focus:border-primary-brand"
          >
            {departments.map((dept) => (
              <option key={dept} value={dept}>
                {dept === "All" ? "All Departments" : dept}
              </option>
            ))}
          </select>

          {/* Version Filter */}
          <select
            value={selectedVersion}
            onChange={(e) => setSelectedVersion(e.target.value)}
            className="py-2 px-3 text-xs rounded-xl bg-surface-muted border border-hairline text-ink focus:outline-none focus:border-primary-brand"
          >
            <option value="All">All Versions</option>
            <option value="Active">Active Only</option>
            <option value="Superseded">Superseded Only</option>
          </select>

          {/* Refresh Button */}
          <button
            type="button"
            onClick={onRefresh}
            className="p-2 rounded-xl border border-hairline text-ink-muted hover:text-ink hover:bg-surface-muted transition-colors"
            title="Refresh documents list"
          >
            <ArrowClockwise size={15} />
          </button>

          {/* Upload Document Action */}
          <button
            type="button"
            onClick={() => setIsUploadModalOpen(true)}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl bg-primary-brand hover:bg-primary-brand-hover text-white shadow-2xs transition-all active:scale-[0.98]"
          >
            <Plus size={14} weight="bold" />
            <span>Upload Document</span>
          </button>
        </div>
      </div>

      {/* Documents Data Table */}
      <div className="p-5 rounded-2xl bg-surface border border-hairline shadow-2xs space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-ink tracking-tight">
              Enterprise Knowledge Catalog
            </h3>
            <p className="text-xs text-ink-muted">
              Showing {filteredDocs.length} of {documents.length} indexed documents
            </p>
          </div>
        </div>

        {loading ? (
          <div className="py-12 flex flex-col items-center justify-center text-ink-muted gap-2">
            <CircleNotch size={24} className="animate-spin text-primary-brand" />
            <span className="text-xs">Loading document repository...</span>
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="py-12 text-center rounded-2xl bg-surface-muted/30 border border-hairline space-y-2">
            <FileText size={32} className="mx-auto text-ink-muted/50" />
            <p className="text-xs font-medium text-ink">No matching documents found</p>
            <p className="text-[11px] text-ink-muted">
              Try adjusting your search criteria or upload a new PDF document.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-hairline text-ink-muted font-semibold">
                  <th className="pb-3 px-3">Document Title</th>
                  <th className="pb-3 px-3">Department</th>
                  <th className="pb-3 px-3">Type</th>
                  <th className="pb-3 px-3">Chunks</th>
                  <th className="pb-3 px-3">Version Status</th>
                  <th className="pb-3 px-3">Ingestion</th>
                  <th className="pb-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {filteredDocs.map((doc) => {
                  const isCurrent = doc.version_status === "current";

                  return (
                    <tr key={doc.id} className="hover:bg-surface-muted/40 transition-colors">
                      {/* Title & Summary */}
                      <td className="py-3 px-3 max-w-xs sm:max-w-sm">
                        <div className="font-semibold text-ink truncate" title={doc.title}>
                          {doc.title}
                        </div>
                        {doc.summary && (
                          <p className="text-[11px] text-ink-muted truncate max-w-xs mt-0.5">
                            {doc.summary}
                          </p>
                        )}
                      </td>

                      {/* Department */}
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span className="px-2.5 py-1 rounded-lg bg-surface border border-hairline text-ink-muted font-medium text-[11px]">
                          {doc.department || "General"}
                        </span>
                      </td>

                      {/* Doc Type */}
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span className="px-2 py-0.5 rounded-md bg-surface-muted text-ink-muted font-mono text-[11px]">
                          {doc.doc_type || "Document"}
                        </span>
                      </td>

                      {/* Chunks */}
                      <td className="py-3 px-3 whitespace-nowrap font-mono text-[11px] text-ink">
                        {doc.chunk_count}
                      </td>

                      {/* Version Toggle */}
                      <td className="py-3 px-3 whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => handleToggleVersion(doc)}
                          title={`Click to mark as ${isCurrent ? "Superseded" : "Active"}`}
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-[11px] font-semibold border transition-all ${
                            isCurrent
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20"
                              : "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30 hover:bg-amber-500/20"
                          }`}
                        >
                          <ArrowsLeftRight size={12} />
                          <span>{isCurrent ? "Active" : "Superseded"}</span>
                        </button>
                      </td>

                      {/* Ingestion Status */}
                      <td className="py-3 px-3 whitespace-nowrap">
                        {doc.ingestion_status === "done" ? (
                          <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium text-[11px]">
                            <CheckCircle size={13} weight="fill" />
                            <span>Indexed</span>
                          </span>
                        ) : doc.ingestion_status === "processing" ? (
                          <span className="inline-flex items-center gap-1 text-primary-brand font-medium text-[11px]">
                            <CircleNotch size={13} className="animate-spin" />
                            <span>Processing</span>
                          </span>
                        ) : doc.ingestion_status === "failed" ? (
                          <span className="inline-flex items-center gap-1 text-rose-500 font-medium text-[11px]">
                            <WarningCircle size={13} weight="fill" />
                            <span>Failed</span>
                          </span>
                        ) : (
                          <span className="text-ink-muted text-[11px] capitalize">
                            {doc.ingestion_status}
                          </span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-3 px-3 text-right whitespace-nowrap">
                        <div className="inline-flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => setSelectedDocForDetail(doc)}
                            className="p-1.5 rounded-lg text-ink-muted hover:text-ink hover:bg-surface-muted transition-colors"
                            title="Inspect Summary & Structure"
                          >
                            <Eye size={16} />
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmDeleteDoc(doc)}
                            className="p-1.5 rounded-lg text-ink-muted hover:text-rose-500 hover:bg-rose-500/10 transition-colors"
                            title="Delete Document"
                          >
                            <Trash size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Document Details Modal */}
      {selectedDocForDetail && (
        <DocumentDetailModal
          document={selectedDocForDetail}
          onClose={() => setSelectedDocForDetail(null)}
        />
      )}

      {/* Upload Modal */}
      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUploadSuccess={() => {
          setIsUploadModalOpen(false);
          onRefresh();
        }}
      />

      {/* Delete Confirmation Modal */}
      {confirmDeleteDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="w-full max-w-md bg-surface border border-hairline rounded-3xl p-6 shadow-xl space-y-4 overflow-hidden">
            <div className="w-10 h-10 rounded-2xl bg-rose-500/10 text-rose-500 flex items-center justify-center">
              <Trash size={20} weight="bold" />
            </div>
            <div className="min-w-0">
              <h3 className="text-sm font-bold text-ink">Delete Document</h3>
              <p className="text-xs text-ink-muted mt-1.5 leading-relaxed break-words [overflow-wrap:anywhere]">
                Are you sure you want to permanently delete{" "}
                <strong className="text-ink font-semibold break-all">
                  "{confirmDeleteDoc.title}"
                </strong>{" "}
                and all its {confirmDeleteDoc.chunk_count} indexed chunks? This cannot be undone.
              </p>
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setConfirmDeleteDoc(null)}
                className="px-4 py-2 text-xs font-medium rounded-xl bg-surface border border-hairline text-ink hover:bg-surface-muted transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deletingDocId === confirmDeleteDoc.id}
                onClick={handleDeleteConfirm}
                className="px-4 py-2 text-xs font-semibold rounded-xl bg-rose-600 hover:bg-rose-700 text-white transition-all disabled:opacity-50 flex items-center gap-1.5"
              >
                {deletingDocId === confirmDeleteDoc.id ? (
                  <>
                    <CircleNotch size={13} className="animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <span>Delete Document</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DocumentsTab;
