/**
 * ConflictAlert Component.
 * Owner: P7
 *
 * Renders policy version conflict events defensively.
 * Displays backend `answer` as-is with conflict styling and lists the
 * `citations` array below it (document_id + section_path + source_path).
 */

import React from "react";
import { GitFork, Warning, WarningOctagon } from "@phosphor-icons/react";
import { FinalEvent } from "./types";
import CitationCard from "./CitationCard";

interface ConflictAlertProps {
  finalEvent: FinalEvent;
}

export const ConflictAlert: React.FC<ConflictAlertProps> = ({ finalEvent }) => {
  const displayAnswer =
    typeof finalEvent?.answer === "string" && finalEvent.answer.trim().length > 0
      ? finalEvent.answer
      : "Multiple active policy documents contain contradictory rules for this query. Please confirm which applies or contact the administrator.";

  const validCitations = Array.isArray(finalEvent?.citations)
    ? finalEvent.citations
    : [];

  return (
    <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-ink">
      <div className="flex items-start gap-3">
        <WarningOctagon
          size={22}
          weight="fill"
          className="text-rose-600 dark:text-rose-400 shrink-0 mt-0.5"
        />
        <div className="space-y-3 text-sm leading-relaxed flex-1">
          <div className="flex items-center justify-between gap-2">
            <h4 className="font-semibold text-rose-700 dark:text-rose-300 flex items-center gap-1.5">
              <Warning size={16} className="text-rose-600 dark:text-rose-400" />
              Policy Version Conflict Detected
            </h4>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-surface border border-hairline text-rose-700 dark:text-rose-300 font-medium">
              Action Required
            </span>
          </div>

          <div className="text-ink whitespace-pre-wrap rounded-xl bg-surface p-3.5 border border-hairline shadow-2xs">
            {displayAnswer}
          </div>

          {validCitations.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-ink-muted flex items-center gap-1 mb-1">
                <GitFork size={14} className="text-accent-gold" />
                <span>Referenced Conflicting Documents:</span>
              </div>
              <CitationCard citations={validCitations} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ConflictAlert;
