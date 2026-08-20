/**
 * GlossaryTab Component for Admin Dashboard.
 * Enterprise terminology and acronym expansion dictionary manager.
 */

import React, { useState } from "react";
import {
  BookOpen,
  Plus,
  Trash,
  MagnifyingGlass,
  CircleNotch,
  ArrowClockwise,
  X,
  Sparkle,
} from "@phosphor-icons/react";
import { GlossaryEntry } from "../types";

interface GlossaryTabProps {
  entries: GlossaryEntry[];
  loading: boolean;
  onRefresh: () => void;
  onAddTerm: (term: string, expansion: string) => Promise<void>;
  onDeleteTerm: (term: string) => Promise<void>;
}

export const GlossaryTab: React.FC<GlossaryTabProps> = ({
  entries,
  loading,
  onRefresh,
  onAddTerm,
  onDeleteTerm,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newTerm, setNewTerm] = useState("");
  const [newExpansion, setNewExpansion] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deletingTerm, setDeletingTerm] = useState<string | null>(null);

  const filtered = entries.filter((e) => {
    const q = searchQuery.toLowerCase();
    return e.term.toLowerCase().includes(q) || e.expansion.toLowerCase().includes(q);
  });

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTerm.trim() || !newExpansion.trim()) return;
    setIsSubmitting(true);
    try {
      await onAddTerm(newTerm.trim(), newExpansion.trim());
      setIsAddModalOpen(false);
      setNewTerm("");
      setNewExpansion("");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (term: string) => {
    setDeletingTerm(term);
    try {
      await onDeleteTerm(term);
    } finally {
      setDeletingTerm(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Intro & Action Bar */}
      <div className="p-5 rounded-2xl bg-surface border border-hairline shadow-2xs flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <MagnifyingGlass
            size={16}
            className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-muted"
          />
          <input
            type="text"
            placeholder="Search acronyms or term definitions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-xs rounded-xl bg-surface-muted border border-hairline text-ink placeholder:text-ink-muted focus:outline-none focus:border-primary-brand"
          />
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onRefresh}
            className="p-2 rounded-xl border border-hairline text-ink-muted hover:text-ink hover:bg-surface-muted transition-colors"
            title="Refresh glossary"
          >
            <ArrowClockwise size={15} />
          </button>

          <button
            type="button"
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl bg-primary-brand hover:bg-primary-brand-hover text-white shadow-2xs transition-all active:scale-[0.98]"
          >
            <Plus size={14} weight="bold" />
            <span>Add Term</span>
          </button>
        </div>
      </div>

      {/* Glossary Data Table */}
      <div className="p-5 rounded-2xl bg-surface border border-hairline shadow-2xs space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-ink tracking-tight">
              Enterprise Acronym & Terminology Dictionary
            </h3>
            <p className="text-xs text-ink-muted">
              Used automatically during query rewriting (Stage 1) to expand enterprise acronyms before dense retrieval.
            </p>
          </div>
          <span className="text-xs font-mono text-ink-muted">
            {filtered.length} terms
          </span>
        </div>

        {loading ? (
          <div className="py-12 flex flex-col items-center justify-center text-ink-muted gap-2">
            <CircleNotch size={24} className="animate-spin text-primary-brand" />
            <span className="text-xs">Loading glossary...</span>
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-12 text-center rounded-2xl bg-surface-muted/30 border border-hairline space-y-2">
            <BookOpen size={32} className="mx-auto text-ink-muted/50" />
            <p className="text-xs font-medium text-ink">No terms found</p>
            <p className="text-[11px] text-ink-muted">
              Add acronyms like 'DA', 'LOP', or 'ERP' to improve RAG retrieval accuracy.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-hairline text-ink-muted font-semibold">
                  <th className="pb-3 px-3 w-40">Acronym / Term</th>
                  <th className="pb-3 px-3">Canonical Expansion / Definition</th>
                  <th className="pb-3 px-3 text-right w-20">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {filtered.map((item) => (
                  <tr key={item.term} className="hover:bg-surface-muted/40 transition-colors">
                    <td className="py-3 px-3 font-mono font-bold text-primary-brand">
                      {item.term}
                    </td>
                    <td className="py-3 px-3 text-ink">
                      {item.expansion}
                    </td>
                    <td className="py-3 px-3 text-right">
                      <button
                        type="button"
                        disabled={deletingTerm === item.term}
                        onClick={() => handleDelete(item.term)}
                        className="p-1.5 rounded-lg text-ink-muted hover:text-rose-500 hover:bg-rose-500/10 transition-colors"
                        title="Delete term"
                      >
                        {deletingTerm === item.term ? (
                          <CircleNotch size={14} className="animate-spin text-rose-500" />
                        ) : (
                          <Trash size={15} />
                        )}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Term Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="w-full max-w-md bg-surface border border-hairline rounded-3xl p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-hairline pb-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-primary-brand text-white flex items-center justify-center">
                  <Plus size={16} weight="bold" />
                </div>
                <h3 className="text-sm font-bold text-ink">Add Glossary Term</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsAddModalOpen(false)}
                className="p-1 text-ink-muted hover:text-ink"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleAddSubmit} className="space-y-3 text-xs">
              <div>
                <label className="block text-[11px] font-semibold text-ink-muted mb-1">
                  Term / Acronym (e.g. CGPA, DA, LOP)
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. SLA"
                  value={newTerm}
                  onChange={(e) => setNewTerm(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl bg-surface-muted border border-hairline text-ink font-mono focus:outline-none focus:border-primary-brand uppercase"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-ink-muted mb-1">
                  Full Expansion / Definition
                </label>
                <textarea
                  required
                  rows={3}
                  placeholder="e.g. Service Level Agreement for IT & vendor support"
                  value={newExpansion}
                  onChange={(e) => setNewExpansion(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl bg-surface-muted border border-hairline text-ink focus:outline-none focus:border-primary-brand resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-hairline">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-4 py-2 text-xs font-medium rounded-xl bg-surface border border-hairline text-ink hover:bg-surface-muted"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 text-xs font-semibold rounded-xl bg-primary-brand text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-1.5"
                >
                  {isSubmitting ? (
                    <>
                      <CircleNotch size={13} className="animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <span>Add Term</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default GlossaryTab;
