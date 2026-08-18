/**
 * CitationCard Component.
 * Owner: P7
 *
 * Displays inline grounded citations strictly matching Section 5 Citation schema:
 *   - chunk_id: UUID
 *   - document_id: UUID
 *   - section_path: string
 *   - source_path?: string | null
 * Styled with Seal Gold accents.
 */

import React, { useState } from "react";
import { BookmarkSimple, FileText, Check, Copy } from "@phosphor-icons/react";
import { Citation } from "./types";

interface CitationCardProps {
  citations: Citation[];
}

export const CitationCard: React.FC<CitationCardProps> = ({ citations }) => {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  if (!citations || citations.length === 0) return null;

  const handleCopy = (citation: Citation) => {
    const textToCopy = `Section: ${citation.section_path}\nDocument: ${citation.document_id}\nChunk: ${citation.chunk_id}${
      citation.source_path ? `\nSource: ${citation.source_path}` : ""
    }`;
    navigator.clipboard.writeText(textToCopy);
    setCopiedId(citation.chunk_id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="mt-4 pt-3 border-t border-hairline">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-accent-gold mb-2">
        <BookmarkSimple size={14} weight="bold" />
        <span>Grounded Sources ({citations.length})</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {citations.map((cite, index) => {
          const isCopied = copiedId === cite.chunk_id;
          return (
            <div
              key={cite.chunk_id || index}
              className="group relative flex flex-col justify-between p-2.5 rounded-xl border border-hairline bg-surface hover:border-accent-gold/50 transition-colors shadow-2xs"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-1.5 min-w-0">
                  <FileText size={14} className="text-accent-gold shrink-0" />
                  <span className="text-xs font-medium text-ink truncate">
                    {cite.section_path || "General Clause"}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleCopy(cite)}
                  title="Copy citation details"
                  className="p-1 rounded text-ink-muted hover:text-ink hover:bg-surface-muted transition-colors"
                >
                  {isCopied ? (
                    <Check size={12} weight="bold" className="text-emerald-500" />
                  ) : (
                    <Copy size={12} />
                  )}
                </button>
              </div>

              <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-ink-muted font-mono">
                <span className="px-1.5 py-0.5 rounded bg-surface-muted border border-hairline text-ink">
                  Doc: {cite.document_id.slice(0, 8)}...
                </span>
                {cite.source_path && (
                  <span className="truncate max-w-[160px]" title={cite.source_path}>
                    {cite.source_path.split("/").pop() || cite.source_path}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default CitationCard;
