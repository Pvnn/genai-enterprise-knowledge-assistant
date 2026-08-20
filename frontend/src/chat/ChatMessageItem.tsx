/**
 * ChatMessageItem Component.
 * Owner: P7
 *
 * Renders individual user queries and assistant responses.
 * Uses Claude-inspired color palette: Civic Indigo, Warm Paper, Deep Slate, and Seal Gold.
 */

import React, { useState } from "react";
import {
  User,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  WarningCircle,
} from "@phosphor-icons/react";
import { ChatMessage } from "./types";
import CitationCard from "./CitationCard";
import RefusalBanner from "./RefusalBanner";
import ConflictAlert from "./ConflictAlert";
import ClarifyPrompt from "./ClarifyPrompt";
import FeedbackModal from "./FeedbackModal";
import NodiLogo from "./NodiLogo";

interface ChatMessageItemProps {
  message: ChatMessage;
  onClarifyRespond?: (reply: string) => void;
  onFeedbackUpdate?: (messageId: string, vote: "up" | "down") => void;
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  message,
  onClarifyRespond,
  onFeedbackUpdate,
}) => {
  const [copied, setCopied] = useState(false);
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false);
  const [initialVote, setInitialVote] = useState<boolean>(true);

  const isUser = message.role === "user";

  const handleCopy = () => {
    const text = message.content || message.final?.answer || "";
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleOpenFeedback = (upVote: boolean) => {
    setInitialVote(upVote);
    setFeedbackModalOpen(true);
  };

  return (
    <div
      className={`py-4 px-4 sm:px-5 rounded-2xl transition-colors ${
        isUser
          ? "bg-surface-muted border border-hairline"
          : "bg-surface border border-hairline shadow-xs"
      }`}
    >
      <div className="flex items-start gap-3.5">
        {/* Role Icon */}
        <div
          className={`w-7 h-7 rounded-xl flex items-center justify-center shrink-0 mt-0.5 ${
            isUser
              ? "bg-surface-elevated text-ink border border-hairline"
              : "bg-surface border border-hairline text-primary-brand shadow-xs"
          }`}
        >
          {isUser ? (
            <User size={15} weight="bold" />
          ) : (
            <NodiLogo size={18} className="text-primary-brand" />
          )}
        </div>

        {/* Message Content Body */}
        <div className="flex-1 min-w-0 space-y-3">
          {/* Header row */}
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-ink">
              {isUser ? "You" : "NODI"}
            </span>
            <span className="text-[11px] text-ink-muted font-mono">
              {new Date(message.timestamp).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </div>

          {/* Streaming loading placeholder when no tokens arrived yet */}
          {!isUser &&
            message.status === "streaming" &&
            !message.content &&
            !message.clarify &&
            !message.final && (
              <div className="flex items-center gap-2 text-xs text-ink-muted py-1">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent-gold animate-bounce" />
                  <span className="w-1.5 h-1.5 rounded-full bg-accent-gold animate-bounce [animation-delay:0.2s]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-accent-gold animate-bounce [animation-delay:0.4s]" />
                </div>
                <span>Retrieving and routing policy passages...</span>
              </div>
            )}

          {/* Error display */}
          {message.status === "error" && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-600 dark:text-rose-400">
              <WarningCircle size={16} weight="bold" className="shrink-0" />
              <span>{message.errorDetail || "An error occurred while answering."}</span>
            </div>
          )}

          {/* Clarifying Question (Priority 2 / Stage 1) */}
          {message.clarify && onClarifyRespond && (
            <ClarifyPrompt
              clarifyEvent={message.clarify}
              onRespond={onClarifyRespond}
            />
          )}

          {/* Refusal Banner (Low Confidence) */}
          {message.final?.refused && (
            <RefusalBanner finalEvent={message.final} />
          )}

          {/* Conflict Alert (Conflicting Policies) */}
          {message.final?.conflict && !message.final?.refused && (
            <ConflictAlert finalEvent={message.final} />
          )}

          {/* Standard Text or Grounded Answer */}
          {(!message.final?.conflict || message.final?.refused) &&
            message.content && (
              <div className="text-sm text-ink leading-relaxed whitespace-pre-wrap break-words">
                {message.content}
                {message.status === "streaming" && (
                  <span className="inline-block w-2 h-4 ml-1 bg-accent-gold animate-cursor-pulse align-middle" />
                )}
              </div>
            )}

          {/* Citations list for standard final events */}
          {message.final &&
            !message.final.conflict &&
            message.final.citations &&
            message.final.citations.length > 0 && (
              <CitationCard citations={message.final.citations} />
            )}

          {/* Action Row for Assistant Messages */}
          {!isUser && message.status === "done" && (
            <div className="flex items-center justify-between pt-2 border-t border-hairline text-xs text-ink-muted">
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={handleCopy}
                  className="flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-surface-muted text-ink-muted hover:text-ink transition-colors"
                  title="Copy answer"
                >
                  {copied ? (
                    <Check size={13} weight="bold" className="text-emerald-500" />
                  ) : (
                    <Copy size={13} />
                  )}
                  <span>{copied ? "Copied" : "Copy"}</span>
                </button>
              </div>

              {/* Feedback Controls (Priority 2) */}
              <div className="flex items-center gap-1">
                <span className="text-[11px] text-ink-muted mr-1">
                  Was this helpful?
                </span>
                <button
                  type="button"
                  onClick={() => handleOpenFeedback(true)}
                  className={`p-1.5 rounded-lg transition-colors ${
                    message.feedbackSubmitted === "up"
                      ? "text-emerald-600 bg-emerald-500/10"
                      : "text-ink-muted hover:text-emerald-600 hover:bg-surface-muted"
                  }`}
                  title="Thumbs up"
                >
                  <ThumbsUp
                    size={14}
                    weight={message.feedbackSubmitted === "up" ? "fill" : "regular"}
                  />
                </button>
                <button
                  type="button"
                  onClick={() => handleOpenFeedback(false)}
                  className={`p-1.5 rounded-lg transition-colors ${
                    message.feedbackSubmitted === "down"
                      ? "text-rose-600 bg-rose-500/10"
                      : "text-ink-muted hover:text-rose-600 hover:bg-surface-muted"
                  }`}
                  title="Thumbs down"
                >
                  <ThumbsDown
                    size={14}
                    weight={message.feedbackSubmitted === "down" ? "fill" : "regular"}
                  />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Feedback Modal */}
      <FeedbackModal
        isOpen={feedbackModalOpen}
        onClose={() => setFeedbackModalOpen(false)}
        initialVote={initialVote}
        messageId={message.id}
        onSubmitted={(vote) => onFeedbackUpdate?.(message.id, vote)}
      />
    </div>
  );
};

export default ChatMessageItem;
