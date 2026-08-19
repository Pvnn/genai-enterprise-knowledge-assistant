/**
 * ClarifyPrompt Component.
 * Owner: P7
 *
 * Renders Stage 1 clarifying questions (type: "clarify").
 * Prompts user for missing department or role context.
 */

import React, { useState } from "react";
import { Question, PaperPlaneRight, Sparkle } from "@phosphor-icons/react";
import { ClarifyEvent } from "./types";

interface ClarifyPromptProps {
  clarifyEvent: ClarifyEvent;
  onRespond: (reply: string) => void;
}

export const ClarifyPrompt: React.FC<ClarifyPromptProps> = ({
  clarifyEvent,
  onRespond,
}) => {
  const [response, setResponse] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!response.trim()) return;
    onRespond(response.trim());
    setResponse("");
  };

  const quickRoles = [
    "Computer Science Faculty",
    "Undergraduate Student",
    "Postgraduate Scholar",
    "Human Resources Staff",
    "Administrative Officer",
  ];

  return (
    <div className="rounded-xl border border-primary-brand/30 bg-primary-brand-subtle/40 p-4 text-ink">
      <div className="flex items-start gap-3">
        <Question
          size={20}
          weight="bold"
          className="text-primary-brand shrink-0 mt-0.5"
        />
        <div className="space-y-3 text-sm flex-1">
          <div className="flex items-center justify-between">
            <h4 className="font-semibold text-ink flex items-center gap-1.5">
              <Sparkle size={14} className="text-accent-gold" />
              Clarification Requested
            </h4>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-surface border border-hairline text-ink-muted font-medium">
              Context Required
            </span>
          </div>

          <p className="text-ink font-medium leading-relaxed">
            {clarifyEvent.question}
          </p>

          <div className="flex flex-wrap gap-1.5 pt-1">
            {quickRoles.map((role) => (
              <button
                key={role}
                type="button"
                onClick={() => onRespond(role)}
                className="px-2.5 py-1 text-xs rounded-lg bg-surface border border-hairline text-ink hover:opacity-90 transition-colors shadow-2xs"
              >
                {role}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="flex gap-2 pt-1">
            <input
              type="text"
              value={response}
              onChange={(e) => setResponse(e.target.value)}
              placeholder="Provide specific department, program, or role..."
              className="flex-1 px-3 py-1.5 text-xs rounded-xl border border-hairline bg-surface text-ink placeholder-ink-muted focus:outline-none focus:ring-2 focus:ring-primary-brand/30"
            />
            <button
              type="submit"
              disabled={!response.trim()}
              className="px-3.5 py-1.5 text-xs font-medium rounded-xl bg-primary-brand hover:opacity-90 text-white disabled:opacity-50 transition-colors flex items-center gap-1"
            >
              <span>Submit</span>
              <PaperPlaneRight size={12} weight="bold" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ClarifyPrompt;
