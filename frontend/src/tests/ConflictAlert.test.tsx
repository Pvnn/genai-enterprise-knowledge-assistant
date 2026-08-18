/**
 * Unit tests for ConflictAlert.tsx.
 * Owner: P7
 *
 * Tests:
 *   - Correct rendering with a well-formed conflict event
 *   - Graceful degradation when conflict is null, undefined, or unexpected shape
 *   - Graceful degradation when answer or citations are missing or empty
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import ConflictAlert from "../chat/ConflictAlert";
import { FinalEvent } from "../chat/types";

describe("ConflictAlert.tsx", () => {
  it("renders correctly with a well-formed conflict payload and citations", () => {
    const wellFormedEvent: FinalEvent = {
      type: "final",
      answer: "Circular 2023 states 15 days leave, but Circular 2025 states 20 days leave.",
      citations: [
        {
          chunk_id: "chunk-uuid-1",
          document_id: "doc-uuid-2023",
          section_path: "Leave / Clause 4",
          source_path: "circular_2023.pdf",
        },
        {
          chunk_id: "chunk-uuid-2",
          document_id: "doc-uuid-2025",
          section_path: "Leave / Clause 6",
          source_path: "circular_2025.pdf",
        },
      ],
      confidence: 0.85,
      refused: false,
      conflict: true,
    };

    render(<ConflictAlert finalEvent={wellFormedEvent} />);

    expect(screen.getByText("Policy Version Conflict Detected")).toBeInTheDocument();
    expect(screen.getByText("Action Required")).toBeInTheDocument();
    expect(
      screen.getByText("Circular 2023 states 15 days leave, but Circular 2025 states 20 days leave.")
    ).toBeInTheDocument();
    expect(screen.getByText("Referenced Conflicting Documents:")).toBeInTheDocument();
    expect(screen.getByText("Leave / Clause 4")).toBeInTheDocument();
    expect(screen.getByText("Leave / Clause 6")).toBeInTheDocument();
  });

  it("degrades gracefully when conflict is boolean or undefined without crashing", () => {
    const eventWithUndefinedConflict = {
      type: "final",
      answer: "Discrepancy detected between policies.",
      citations: [],
      confidence: 0.75,
      refused: false,
      conflict: undefined as unknown as boolean,
    } as FinalEvent;

    render(<ConflictAlert finalEvent={eventWithUndefinedConflict} />);

    expect(screen.getByText("Policy Version Conflict Detected")).toBeInTheDocument();
    expect(screen.getByText("Discrepancy detected between policies.")).toBeInTheDocument();
  });

  it("degrades gracefully with fallback text when answer is null or empty", () => {
    const eventWithNullAnswer = {
      type: "final",
      answer: "" as unknown as string,
      citations: [],
      confidence: 0.7,
      refused: false,
      conflict: true,
    } as FinalEvent;

    render(<ConflictAlert finalEvent={eventWithNullAnswer} />);

    expect(screen.getByText("Policy Version Conflict Detected")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Multiple active policy documents contain contradictory rules for this query. Please confirm which applies or contact the administrator."
      )
    ).toBeInTheDocument();
  });

  it("degrades gracefully when citations is null or not an array", () => {
    const eventWithInvalidCitations = {
      type: "final",
      answer: "Contradictory grading policy.",
      citations: null as unknown as [],
      confidence: 0.8,
      refused: false,
      conflict: true,
    } as FinalEvent;

    render(<ConflictAlert finalEvent={eventWithInvalidCitations} />);

    expect(screen.getByText("Policy Version Conflict Detected")).toBeInTheDocument();
    expect(screen.getByText("Contradictory grading policy.")).toBeInTheDocument();
    expect(screen.queryByText("Referenced Conflicting Documents:")).not.toBeInTheDocument();
  });
});
