/**
 * Unit tests for API client (client.ts).
 * Owner: P7
 *
 * Tests:
 *   - submitFeedback sending correct FeedbackRequest shape
 *   - streamChat SSE dispatching for token, clarify, final
 *   - streamChat forward-compatibility ignoring unrecognized event types
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { submitFeedback, streamChat } from "../api/client";
import { ClarifyEvent, FinalEvent, TokenEvent } from "../chat/types";

describe("api/client.ts", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("submitFeedback", () => {
    it("sends the exact FeedbackRequest shape to POST /feedback", async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "ok" }),
      });
      globalThis.fetch = mockFetch;

      const payload = {
        query_id: "test-query-uuid-123",
        thumbs_up_down: true,
        comment: "Accurate citation provided.",
      };

      const result = await submitFeedback(payload);

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toContain("/feedback");
      expect(options.method).toBe("POST");
      expect(options.headers["Content-Type"]).toBe("application/json");

      const parsedBody = JSON.parse(options.body);
      expect(parsedBody).toEqual({
        query_id: "test-query-uuid-123",
        thumbs_up_down: true,
        comment: "Accurate citation provided.",
      });

      expect(result).toEqual({ status: "ok" });
    });

    it("attaches Authorization header when access token is present", async () => {
      localStorage.setItem("access_token", "mock-jwt-token-xyz");

      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "ok" }),
      });
      globalThis.fetch = mockFetch;

      await submitFeedback({
        query_id: "test-query-uuid",
        thumbs_up_down: false,
        comment: null,
      });

      const [, options] = mockFetch.mock.calls[0];
      expect(options.headers.Authorization).toBe("Bearer mock-jwt-token-xyz");
    });

    it("throws a descriptive error when server returns non-ok status", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ error: "bad_request", detail: "Invalid query_id format" }),
      });

      await expect(
        submitFeedback({
          query_id: "invalid-id",
          thumbs_up_down: true,
        })
      ).rejects.toThrow("Invalid query_id format");
    });
  });

  describe("streamChat SSE client", () => {
    function createMockStream(chunks: string[]) {
      const encoder = new TextEncoder();
      let index = 0;
      return new ReadableStream({
        pull(controller) {
          if (index < chunks.length) {
            controller.enqueue(encoder.encode(chunks[index]));
            index++;
          } else {
            controller.close();
          }
        },
      });
    }

    it("dispatches token, clarify, and final events correctly", async () => {
      const ssePayloads = [
        'data: {"type":"token","content":"According to "}\n\n',
        'data: {"type":"token","content":"Section 4.1..."}\n\n',
        'data: {"type":"clarify","question":"Please specify your department."}\n\n',
        'data: {"type":"final","answer":"Leave policy details.","citations":[{"chunk_id":"c1","document_id":"d1","section_path":"4.1","source_path":"doc.pdf"}],"confidence":0.92,"refused":false,"refusal_reason":null,"conflict":false}\n\n',
      ];

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        body: createMockStream(ssePayloads),
      });

      const onToken = vi.fn();
      const onClarify = vi.fn();
      const onFinal = vi.fn();
      const onError = vi.fn();

      await streamChat(
        { query: "Leave rules", tenant_id: "00000000-0000-0000-0000-000000000001" },
        { onToken, onClarify, onFinal, onError }
      );

      expect(onToken).toHaveBeenCalledTimes(2);
      expect(onToken).toHaveBeenNthCalledWith(1, { type: "token", content: "According to " } as TokenEvent);
      expect(onToken).toHaveBeenNthCalledWith(2, { type: "token", content: "Section 4.1..." } as TokenEvent);

      expect(onClarify).toHaveBeenCalledTimes(1);
      expect(onClarify).toHaveBeenCalledWith({
        type: "clarify",
        question: "Please specify your department.",
      } as ClarifyEvent);

      expect(onFinal).toHaveBeenCalledTimes(1);
      expect(onFinal).toHaveBeenCalledWith({
        type: "final",
        answer: "Leave policy details.",
        citations: [
          { chunk_id: "c1", document_id: "d1", section_path: "4.1", source_path: "doc.pdf" },
        ],
        confidence: 0.92,
        refused: false,
        refusal_reason: null,
        conflict: false,
      } as FinalEvent);

      expect(onError).not.toHaveBeenCalled();
    });

    it("maintains forward compatibility: ignores unrecognized event types without breaking", async () => {
      const ssePayloads = [
        'data: {"type":"heartbeat","timestamp":"2026-08-18T12:00:00Z"}\n\n',
        'data: {"type":"token","content":"Valid token"}\n\n',
        'data: {"type":"experimental_debug_trace","trace_id":"xyz"}\n\n',
        'data: {"type":"final","answer":"Done","citations":[],"confidence":0.88,"refused":false,"conflict":false}\n\n',
      ];

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        body: createMockStream(ssePayloads),
      });

      const onToken = vi.fn();
      const onFinal = vi.fn();
      const onError = vi.fn();

      await streamChat(
        { query: "Policy test", tenant_id: "tenant-1" },
        { onToken, onFinal, onError }
      );

      expect(onToken).toHaveBeenCalledTimes(1);
      expect(onToken).toHaveBeenCalledWith({ type: "token", content: "Valid token" });

      expect(onFinal).toHaveBeenCalledTimes(1);
      expect(onFinal).toHaveBeenCalledWith({
        type: "final",
        answer: "Done",
        citations: [],
        confidence: 0.88,
        refused: false,
        conflict: false,
      });

      expect(onError).not.toHaveBeenCalled();
    });

    it("handles chunked split lines across buffer boundaries", async () => {
      const splitChunks = [
        'data: {"type":"to',
        'ken","content":"Spl',
        'it text"}\n\n',
        'data: {"type":"final","answer":"All done","citations":[],"confidence":1.0,"refused":false,"conflict":false}\n\n',
      ];

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        body: createMockStream(splitChunks),
      });

      const onToken = vi.fn();
      const onFinal = vi.fn();

      await streamChat(
        { query: "Buffer split test", tenant_id: "tenant-1" },
        { onToken, onFinal }
      );

      expect(onToken).toHaveBeenCalledWith({ type: "token", content: "Split text" });
      expect(onFinal).toHaveBeenCalledTimes(1);
    });
  });
});
