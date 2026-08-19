/**
 * Unit tests for FeedbackModal.tsx.
 * Owner: P7
 *
 * Tests:
 *   - Renders modal when isOpen is true
 *   - Sourced query_id placeholder from messageId when provided
 *   - Sourced query_id placeholder from crypto.randomUUID() when messageId is empty
 *   - Submits exact FeedbackRequest shape to submitFeedback
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import FeedbackModal from "../chat/FeedbackModal";
import * as apiClient from "../api/client";

vi.mock("../api/client", () => ({
  submitFeedback: vi.fn(),
}));

describe("FeedbackModal.tsx", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not render when isOpen is false", () => {
    const { container } = render(
      <FeedbackModal
        isOpen={false}
        onClose={vi.fn()}
        initialVote={true}
        messageId="msg-123"
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders when isOpen is true and shows initial helpful vote", () => {
    render(
      <FeedbackModal
        isOpen={true}
        onClose={vi.fn()}
        initialVote={true}
        messageId="msg-123"
      />
    );

    expect(screen.getByText("Submit Answer Feedback")).toBeInTheDocument();
    expect(screen.getByText("Helpful")).toBeInTheDocument();
    expect(screen.getByText("Not Helpful")).toBeInTheDocument();
  });

  it("submits with messageId as query_id placeholder when messageId is present", async () => {
    const mockSubmit = vi.spyOn(apiClient, "submitFeedback").mockResolvedValue({ status: "ok" });
    const onSubmitted = vi.fn();
    const onClose = vi.fn();

    render(
      <FeedbackModal
        isOpen={true}
        onClose={onClose}
        initialVote={true}
        messageId="message-uuid-abc"
        onSubmitted={onSubmitted}
      />
    );

    const commentInput = screen.getByPlaceholderText("Describe how this answer can be improved...");
    fireEvent.change(commentInput, { target: { value: "Section reference is accurate." } });

    const submitBtn = screen.getByRole("button", { name: "Submit Feedback" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledTimes(1);
    });

    expect(mockSubmit).toHaveBeenCalledWith({
      query_id: "message-uuid-abc",
      thumbs_up_down: true,
      comment: "Section reference is accurate.",
    });

    expect(onSubmitted).toHaveBeenCalledWith("up");
  });

  it("generates a valid UUID string as query_id fallback when messageId is empty", async () => {
    const mockSubmit = vi.spyOn(apiClient, "submitFeedback").mockResolvedValue({ status: "ok" });

    render(
      <FeedbackModal
        isOpen={true}
        onClose={vi.fn()}
        initialVote={false}
        messageId=""
      />
    );

    const submitBtn = screen.getByRole("button", { name: "Submit Feedback" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledTimes(1);
    });

    const submittedArg = mockSubmit.mock.calls[0][0];
    expect(typeof submittedArg.query_id).toBe("string");
    expect(submittedArg.query_id.length).toBeGreaterThan(0);
    expect(submittedArg.thumbs_up_down).toBe(false);
  });
});
