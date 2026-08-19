/**
 * DocumentsLibrary Component.
 * Owner: P7
 *
 * Provides an institutional knowledge library explorer where users can inspect
 * verified documents, department circulars, effective dates, and chunk indexing status.
 */

import React, { useState, useEffect } from "react";
import {
  FileText,
  MagnifyingGlass,
  Funnel,
  CheckCircle,
  ClockCounterClockwise,
  ChatCircleDots,
  Buildings,
  Hash,
  Calendar,
} from "@phosphor-icons/react";
import { DocumentItem } from "./types";
import { fetchDocuments } from "../api/client";

interface DocumentsLibraryProps {
  tenantId: string;
  onAskAboutDocument: (documentTitle: string) => void;
}

export const DocumentsLibrary: React.FC<DocumentsLibraryProps> = ({
  tenantId,
  onAskAboutDocument,
}) => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDept, setSelectedDept] = useState("All");
  const [selectedStatus, setSelectedStatus] = useState("All");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    fetchDocuments(tenantId).then((docs) => {
      if (isMounted) {
        setDocuments(docs);
        setLoading(false);
      }
    });
    return () => {
      isMounted = false;
    };
  }, [tenantId]);

  const departments = [
    "All",
    "Academic Affairs",
    "Human Resources",
    "Finance & Accounts",
    "Procurement",
    "Research & Development",
  ];

  const filteredDocs = documents.filter((doc) => {
    const matchesSearch =
      doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.department.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (doc.summary && doc.summary.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesDept = selectedDept === "All" || doc.department === selectedDept;
    const matchesStatus =
      selectedStatus === "All" ||
      (selectedStatus === "Active" && doc.version_status === "current") ||
      (selectedStatus === "Superseded" && doc.version_status === "superseded");

    return matchesSearch && matchesDept && matchesStatus;
  });

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 md:px-8 py-6 space-y-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header Title & Intro */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-hairline">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Buildings size={20} className="text-primary-brand" />
              <h2 className="text-xl font-bold text-ink tracking-tight">
                Institutional Document Library
              </h2>
            </div>
            <p className="text-xs sm:text-sm text-ink-muted">
              Explore verified policy circulars, syllabi, and administrative regulations indexed in this knowledge base.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-mono px-3 py-1.5 rounded-xl bg-surface border border-hairline text-ink-muted">
              {filteredDocs.length} of {documents.length} Documents
            </span>
          </div>
        </div>

        {/* Search & Filter Controls */}
        <div className="flex flex-col md:flex-row gap-3">
          <div className="relative flex-1">
            <MagnifyingGlass
              size={16}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-muted"
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search circulars, regulations, or keywords..."
              className="w-full pl-10 pr-4 py-2.5 text-xs sm:text-sm rounded-xl border border-hairline bg-surface text-ink placeholder-ink-muted focus:outline-none focus:ring-2 focus:ring-primary-brand/30 shadow-2xs"
            />
          </div>

          {/* Department & Status Filter Selectors */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
              <Funnel size={15} className="text-ink-muted shrink-0" />
              {departments.map((dept) => (
                <button
                  key={dept}
                  type="button"
                  onClick={() => setSelectedDept(dept)}
                  className={`px-3 py-1.5 rounded-xl text-xs whitespace-nowrap border transition-all ${
                    selectedDept === dept
                      ? "bg-primary-brand text-white border-primary-brand shadow-2xs font-medium"
                      : "bg-surface border-hairline text-ink-muted hover:text-ink hover:bg-surface-muted"
                  }`}
                >
                  {dept}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1.5 pl-0 sm:pl-2 sm:border-l border-hairline">
              {["All", "Active", "Superseded"].map((status) => (
                <button
                  key={status}
                  type="button"
                  onClick={() => setSelectedStatus(status)}
                  className={`px-2.5 py-1.5 rounded-xl text-xs whitespace-nowrap border transition-all ${
                    selectedStatus === status
                      ? "bg-accent-gold text-white border-accent-gold font-medium shadow-2xs"
                      : "bg-surface border-hairline text-ink-muted hover:text-ink hover:bg-surface-muted"
                  }`}
                >
                  {status}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Documents Grid */}
        {loading ? (
          <div className="py-16 text-center text-xs text-ink-muted">
            Loading institutional documents...
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="py-16 text-center space-y-2 rounded-2xl border border-hairline bg-surface p-8">
            <FileText size={32} className="mx-auto text-ink-muted opacity-60" />
            <p className="text-sm font-medium text-ink">No matching documents found</p>
            <p className="text-xs text-ink-muted">
              Try adjusting your search query or department filter.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredDocs.map((doc) => {
              const isCurrent = doc.version_status === "current";
              return (
                <div
                  key={doc.id}
                  className="rounded-2xl border border-hairline bg-surface p-5 hover:border-accent-gold/60 transition-all shadow-2xs flex flex-col justify-between space-y-4 group"
                >
                  <div className="space-y-2.5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-xl bg-surface-muted border border-hairline flex items-center justify-center text-primary-brand group-hover:text-accent-gold transition-colors shrink-0">
                          <FileText size={16} weight="bold" />
                        </div>
                        <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-surface-muted border border-hairline text-ink-muted">
                          {doc.doc_type}
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5">
                        {isCurrent ? (
                          <span className="flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30">
                            <CheckCircle size={12} weight="fill" />
                            <span>Active</span>
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/30">
                            <ClockCounterClockwise size={12} />
                            <span>Superseded</span>
                          </span>
                        )}
                      </div>
                    </div>

                    <h3 className="text-sm font-bold text-ink leading-snug">
                      {doc.title}
                    </h3>

                    {doc.summary && (
                      <p className="text-xs text-ink-muted line-clamp-2 leading-relaxed">
                        {doc.summary}
                      </p>
                    )}
                  </div>

                  <div className="pt-3 border-t border-hairline flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 text-xs text-ink-muted">
                    <div className="flex items-center gap-3 font-mono text-[11px]">
                      <span className="flex items-center gap-1">
                        <Calendar size={13} />
                        <span>{doc.effective_date}</span>
                      </span>
                      {doc.chunk_count && (
                        <span className="flex items-center gap-1">
                          <Hash size={13} />
                          <span>{doc.chunk_count} chunks</span>
                        </span>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => onAskAboutDocument(doc.title)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary-brand-subtle text-primary-brand hover:bg-primary-brand hover:text-white transition-all font-medium self-end sm:self-auto text-xs active:scale-95"
                    >
                      <ChatCircleDots size={14} weight="bold" />
                      <span>Ask About Doc</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentsLibrary;
