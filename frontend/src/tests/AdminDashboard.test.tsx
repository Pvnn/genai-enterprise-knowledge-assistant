/**
 * Unit tests for AdminDashboard.tsx.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import AdminDashboard from "../admin/AdminDashboard";
import * as apiClient from "../api/client";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof apiClient>("../api/client");
  return {
    ...actual,
    fetchAdminAnalytics: vi.fn().mockResolvedValue({
      total_queries: 1420,
      answered_queries: 1318,
      refused_queries: 102,
      avg_confidence: 0.912,
      positive_feedback_count: 512,
      negative_feedback_count: 28,
      csat_percent: 94.8,
      total_documents: 14,
      total_chunks: 482,
      total_members: 38,
      recent_activity: [
        {
          query_id: "q-101",
          raw_query: "What is the maternity leave entitlement?",
          created_at: new Date().toISOString(),
          confidence_score: 0.96,
          answered_or_refused: true,
          feedback_thumbs_up_down: true,
          feedback_comment: "Clear",
        },
      ],
      department_distribution: {
        "Human Resources": 4,
      },
    }),
    fetchAdminDocuments: vi.fn().mockResolvedValue([
      {
        id: "doc-101",
        tenant_id: "00000000-0000-0000-0000-000000000001",
        title: "Staff Code of Conduct 2025",
        department: "Human Resources",
        doc_type: "Policy",
        effective_date: "2025-01-01",
        version_status: "current",
        source_path: "uploads/hr/code.pdf",
        summary: "Staff regulations.",
        section_tree: { "1. Overview": ["Clause 1"] },
        chunk_count: 32,
        ingestion_status: "done",
      },
    ]),
    fetchAdminUsers: vi.fn().mockResolvedValue([
      {
        id: "u-1",
        tenant_id: "00000000-0000-0000-0000-000000000001",
        email: "lead_admin@enterprise.com",
        role: "admin",
      },
    ]),
    fetchAdminGlossary: vi.fn().mockResolvedValue([
      { id: "g-1", term: "PTO", expansion: "Paid Time Off" },
    ]),
  };
});

describe("AdminDashboard.tsx", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem("user_role", "admin");
    localStorage.setItem("tenant_id", "00000000-0000-0000-0000-000000000001");
  });

  it("renders Admin Center header and analytics overview tab by default", async () => {
    render(<AdminDashboard onReturnToChat={vi.fn()} />);

    expect(screen.getByText("Enterprise Admin Center")).toBeInTheDocument();
    expect(screen.getByText("Admin Role")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("1,420")).toBeInTheDocument();
      expect(screen.getByText("91.2%")).toBeInTheDocument();
      expect(screen.getByText("94.8%")).toBeInTheDocument();
      expect(screen.getByText("What is the maternity leave entitlement?")).toBeInTheDocument();
    });
  });

  it("switches to Document Management tab when clicked", async () => {
    render(<AdminDashboard onReturnToChat={vi.fn()} />);

    const docsTabBtn = screen.getByRole("button", { name: /Document Management/i });
    fireEvent.click(docsTabBtn);

    await waitFor(() => {
      expect(screen.getByText("Staff Code of Conduct 2025")).toBeInTheDocument();
      expect(screen.getByText("Upload Document")).toBeInTheDocument();
    });
  });

  it("switches to Enterprise Members tab when clicked", async () => {
    render(<AdminDashboard onReturnToChat={vi.fn()} />);

    const membersTabBtn = screen.getByRole("button", { name: /Enterprise Members/i });
    fireEvent.click(membersTabBtn);

    await waitFor(() => {
      expect(screen.getByText("lead_admin@enterprise.com")).toBeInTheDocument();
      expect(screen.getByText("Invite Member")).toBeInTheDocument();
    });
  });

  it("switches to Glossary & Terminology tab when clicked", async () => {
    render(<AdminDashboard onReturnToChat={vi.fn()} />);

    const glossaryTabBtn = screen.getByRole("button", { name: /Glossary & Terminology/i });
    fireEvent.click(glossaryTabBtn);

    await waitFor(() => {
      expect(screen.getByText("PTO")).toBeInTheDocument();
      expect(screen.getByText("Paid Time Off")).toBeInTheDocument();
    });
  });

  it("triggers onReturnToChat when 'Return to Chat' is clicked", async () => {
    const onReturn = vi.fn();
    render(<AdminDashboard onReturnToChat={onReturn} />);

    await waitFor(() => {
      expect(screen.getByText("Enterprise Admin Center")).toBeInTheDocument();
    });

    const returnBtn = screen.getByRole("button", { name: /Return to Chat/i });
    fireEvent.click(returnBtn);

    expect(onReturn).toHaveBeenCalledTimes(1);
  });
});
