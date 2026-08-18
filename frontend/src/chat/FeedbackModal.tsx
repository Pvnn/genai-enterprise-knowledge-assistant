/**
 * FeedbackModal Component (Priority 2).
 * Owner: P7
 *
 * Captures user feedback on assistant answers and submits to POST /feedback.
 * Styled with Claude-inspired palette.
 */

import React, { useState } from "react";
import { ThumbsUp, ThumbsDown, X, CheckCircle, Warning } from "@phosphor-icons/react";
import { submitFeedback } from "../api/client";

interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialVote: boolean; // true = up, false = down
  messageId: string;
  onSubmitted?: (vote: "up" | "down") => void;
}

export const FeedbackModal: React.FC<FeedbackModalProps> = ({
  isOpen,
  onClose,
  initialVote,
  messageId,
  onSubmitted,
}) => {
  const [vote, setVote] = useState<boolean>(initialVote);
  const [comment, setComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      // TODO: replace once backend confirms query_id source.
      // Schema gap: FinalEvent in Section 5 does not provide query_id, but POST /feedback requires it.
      // Owned by P2 (schemas.py) and P4 (generator.py / /chat router).
      const queryIdPlaceholder = messageId || crypto.randomUUID();

      await submitFeedback({
        query_id: queryIdPlaceholder,
        thumbs_up_down: vote,
        comment: comment.trim() || null,
      });

      setIsSuccess(true);
      onSubmitted?.(vote ? "up" : "down");
      setTimeout(() => {
        setIsSuccess(false);
        onClose();
      }, 1200);
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to submit feedback.";
      setSubmitError(errorMsg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="w-full max-w-md rounded-2xl border border-hairline bg-surface p-6 shadow-2xl space-y-4 text-ink">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-ink">
            Submit Answer Feedback
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-ink-muted hover:text-ink hover:bg-surface-muted transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {isSuccess ? (
          <div className="py-6 flex flex-col items-center justify-center text-center space-y-2 text-emerald-600 dark:text-emerald-400">
            <CheckCircle size={36} weight="fill" />
            <p className="text-sm font-medium">Thank you for your feedback!</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex items-center justify-center gap-4 py-2">
              <button
                type="button"
                onClick={() => setVote(true)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-all ${
                  vote
                    ? "border-emerald-500 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                    : "border-hairline hover:bg-surface-muted text-ink-muted"
                }`}
              >
                <ThumbsUp size={18} weight={vote ? "fill" : "regular"} />
                <span>Helpful</span>
              </button>

              <button
                type="button"
                onClick={() => setVote(false)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-all ${
                  !vote
                    ? "border-rose-500 bg-rose-500/10 text-rose-700 dark:text-rose-300"
                    : "border-hairline hover:bg-surface-muted text-ink-muted"
                }`}
              >
                <ThumbsDown size={18} weight={!vote ? "fill" : "regular"} />
                <span>Not Helpful</span>
              </button>
            </div>

            <div>
              <label
                htmlFor="feedback-comment"
                className="block text-xs font-medium text-ink-muted mb-1"
              >
                Optional Comments (e.g. incorrect section, outdated circular):
              </label>
              <textarea
                id="feedback-comment"
                rows={3}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Describe how this answer can be improved..."
                className="w-full px-3 py-2 text-xs rounded-xl border border-hairline bg-surface-muted text-ink placeholder-ink-muted focus:outline-none focus:ring-2 focus:ring-primary-brand/30"
              />
            </div>

            {submitError && (
              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-700 dark:text-rose-300">
                <Warning size={16} className="shrink-0" />
                <span>{submitError}</span>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-xs font-medium rounded-xl border border-hairline text-ink-muted hover:bg-surface-muted transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-4 py-2 text-xs font-medium rounded-xl bg-primary-brand hover:opacity-90 text-white disabled:opacity-50 transition-colors"
              >
                {isSubmitting ? "Submitting..." : "Submit Feedback"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default FeedbackModal;
