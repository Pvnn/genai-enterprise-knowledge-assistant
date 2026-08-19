/**
 * Unit tests for DocumentsLibrary.tsx.
 * Owner: P7
 *
 * Tests:
 *   - Admin user sees "Upload Document" button
 *   - Normal user does NOT see "Upload Document" button
 *   - Clicking "Upload Document" triggers navigation to /upload
 *   - Search and filter behavior
 *   - "Ask About Doc" button callback
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import DocumentsLibrary from "../chat/DocumentsLibrary";
import * as apiClient from "../api/client";

const mockDocuments = [
  {
    id: "doc-1",
    tenant_id: "tenant-123",
    title: "Institutional Leave Rules 2025",
    department: "Human Resources",
    doc_type: "Policy",
    effective_date: "2025-01-01",
    version_status: "current" as const,
    summary: "Comprehensive leave rules and entitlements.",
    chunk_count: 42,
  },
  {
    id: "doc-2",
    tenant_id: "tenant-123",
    title: "Procurement Manual 2023",
    department: "Procurement",
    doc_type: "Manual",
    effective_date: "2023-11-15",
    version_status: "current" as const,
    summary: "Tender bidding procedures and limits.",
    chunk_count: 30,
  },
];

describe("DocumentsLibrary.tsx", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    vi.spyOn(apiClient, "fetchDocuments").mockResolvedValue(mockDocuments);
  });

  it("renders 'Upload Document' button when userRole is 'admin'", async () => {
    render(
      <DocumentsLibrary
        tenantId="tenant-123"
        onAskAboutDocument={vi.fn()}
        userRole="admin"
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Institutional Leave Rules 2025")).toBeInTheDocument();
    });

    const uploadBtn = screen.getByRole("button", { name: /Upload Document/i });
    expect(uploadBtn).toBeInTheDocument();
  });

  it("does NOT render 'Upload Document' button for a regular user ('member')", async () => {
    render(
      <DocumentsLibrary
        tenantId="tenant-123"
        onAskAboutDocument={vi.fn()}
        userRole="member"
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Institutional Leave Rules 2025")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: /Upload Document/i })).not.toBeInTheDocument();
  });

  it("does NOT render 'Upload Document' button when no role is provided and localStorage has no admin role", async () => {
    render(
      <DocumentsLibrary
        tenantId="tenant-123"
        onAskAboutDocument={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Institutional Leave Rules 2025")).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: /Upload Document/i })).not.toBeInTheDocument();
  });

  it("calls onNavigateUpload callback when admin clicks 'Upload Document'", async () => {
    const onNavigateUpload = vi.fn();

    render(
      <DocumentsLibrary
        tenantId="tenant-123"
        onAskAboutDocument={vi.fn()}
        userRole="admin"
        onNavigateUpload={onNavigateUpload}
      />
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Upload Document/i })).toBeInTheDocument();
    });

    const uploadBtn = screen.getByRole("button", { name: /Upload Document/i });
    fireEvent.click(uploadBtn);

    expect(onNavigateUpload).toHaveBeenCalledTimes(1);
  });

  it("allows regular users to click 'Ask About Doc' with the correct document title", async () => {
    const onAskAboutDocument = vi.fn();

    render(
      <DocumentsLibrary
        tenantId="tenant-123"
        onAskAboutDocument={onAskAboutDocument}
        userRole="member"
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Institutional Leave Rules 2025")).toBeInTheDocument();
    });

    const askButtons = screen.getAllByRole("button", { name: /Ask About Doc/i });
    expect(askButtons.length).toBe(2);

    fireEvent.click(askButtons[0]);
    expect(onAskAboutDocument).toHaveBeenCalledWith("Institutional Leave Rules 2025");
  });

  it("filters documents when searching in the search bar", async () => {
    render(
      <DocumentsLibrary
        tenantId="tenant-123"
        onAskAboutDocument={vi.fn()}
        userRole="member"
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Institutional Leave Rules 2025")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search circulars, regulations/i);
    fireEvent.change(searchInput, { target: { value: "Procurement" } });

    expect(screen.getByText("Procurement Manual 2023")).toBeInTheDocument();
    expect(screen.queryByText("Institutional Leave Rules 2025")).not.toBeInTheDocument();
  });
});
