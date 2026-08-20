/**
 * Unit tests for UploadPage.tsx.
 * Owner: P7
 *
 * Tests:
 *   - Renders upload form for admin
 *   - Dispatches uploadDocument via client helper
 *   - Polls getDocumentStatus until done
 *   - Displays error messages on failure
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import UploadPage from "../upload/UploadPage";
import * as apiClient from "../api/client";

vi.mock("../api/client", () => ({
  uploadDocument: vi.fn(),
  getDocumentStatus: vi.fn(),
}));

describe("UploadPage.tsx", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders upload form fields correctly", () => {
    render(<UploadPage />);

    expect(screen.getByRole("heading", { name: "Upload Document" })).toBeInTheDocument();
    expect(screen.getByLabelText(/PDF File/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/e.g. Human Resources/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/e.g. Policy/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload" })).toBeInTheDocument();
  });

  it("requires PDF file, department, and doc_type before submitting", async () => {
    render(<UploadPage />);

    const uploadBtn = screen.getByRole("button", { name: "Upload" });
    fireEvent.click(uploadBtn);

    expect(await screen.findByText("Please select a PDF file.")).toBeInTheDocument();
    expect(apiClient.uploadDocument).not.toHaveBeenCalled();
  });

  it("calls uploadDocument with form values and transitions status", async () => {
    vi.mocked(apiClient.uploadDocument).mockResolvedValue({
      document_id: "doc-uuid-999",
      ingestion_status: "pending",
    });
    vi.mocked(apiClient.getDocumentStatus).mockResolvedValue({
      document_id: "doc-uuid-999",
      ingestion_status: "done",
      detail: null,
    });

    render(<UploadPage />);

    const fileInput = screen.getByLabelText(/PDF File/i);
    const deptInput = screen.getByPlaceholderText(/e.g. Human Resources/i);
    const docTypeInput = screen.getByPlaceholderText(/e.g. Policy/i);

    const testFile = new File(["test-pdf-bytes"], "policy.pdf", { type: "application/pdf" });
    Object.defineProperty(fileInput, "files", {
      value: [testFile],
    });

    fireEvent.change(deptInput, { target: { value: "Finance & Accounts" } });
    fireEvent.change(docTypeInput, { target: { value: "Regulation" } });

    const uploadBtn = screen.getByRole("button", { name: "Upload" });
    fireEvent.click(uploadBtn);

    await waitFor(() => {
      expect(apiClient.uploadDocument).toHaveBeenCalledWith(
        testFile,
        "Finance & Accounts",
        "Regulation"
      );
    });

    expect(await screen.findByText("Document ID: doc-uuid-999")).toBeInTheDocument();
  });

  it("displays server error when uploadDocument fails", async () => {
    vi.mocked(apiClient.uploadDocument).mockRejectedValue(
      new Error("Only admin users may upload documents.")
    );

    render(<UploadPage />);

    const fileInput = screen.getByLabelText(/PDF File/i);
    const deptInput = screen.getByPlaceholderText(/e.g. Human Resources/i);
    const docTypeInput = screen.getByPlaceholderText(/e.g. Policy/i);

    const testFile = new File(["test-pdf-bytes"], "policy.pdf", { type: "application/pdf" });
    Object.defineProperty(fileInput, "files", {
      value: [testFile],
    });

    fireEvent.change(deptInput, { target: { value: "HR" } });
    fireEvent.change(docTypeInput, { target: { value: "Policy" } });

    const uploadBtn = screen.getByRole("button", { name: "Upload" });
    fireEvent.click(uploadBtn);

    expect(
      await screen.findByText("Only admin users may upload documents.")
    ).toBeInTheDocument();
  });
});
