/**
 * RefusalBanner Component.
 * Owner: P7
 *
 * Renders low-confidence refusal events (refused: true).
 * Strictly renders backend refusal_reason or answer string as-is with alert styling.
 * Uses Seal Gold accent borders and warm background styling.
 */

import React from "react";
import { WarningCircle, Info } from "@phosphor-icons/react";
import { FinalEvent } from "./types";

interface RefusalBannerProps {
  finalEvent: FinalEvent;
}

export const RefusalBanner: React.FC<RefusalBannerProps> = ({ finalEvent }) => {
  const displayText =
    finalEvent.refusal_reason ||
    finalEvent.answer ||
    "I could not find a passage in the current policy documents that directly answers this.";

  const formattedConfidence = (finalEvent.confidence * 100).toFixed(0);

  return (
    <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-ink">
      <div className="flex items-start gap-3">
        <WarningCircle
          size={20}
          weight="fill"
          className="text-accent-gold shrink-0 mt-0.5"
        />
        <div className="space-y-2 text-sm leading-relaxed flex-1">
          <div className="flex items-center justify-between gap-2">
            <h4 className="font-semibold text-ink">
              Low-Confidence Policy Retrieval
            </h4>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-surface border border-hairline text-accent-gold font-medium">
              Confidence: {formattedConfidence}%
            </span>
          </div>

          <p className="text-ink whitespace-pre-wrap">
            {displayText}
          </p>

          <div className="pt-2 flex items-center gap-1.5 text-xs text-ink-muted">
            <Info size={14} className="shrink-0 text-accent-gold" />
            <span>
              Tip: Try rephrasing your query or specifying relevant department keywords.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RefusalBanner;
