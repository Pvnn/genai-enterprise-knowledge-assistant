# Grounded Generation & Pipeline Orchestration

**Owner:** P4
**Stage:** 5 (this file also carries out the full Stage 1-5 call order)
**Priority:** 1
**Files:** `backend/app/generation/generator.py`, `backend/app/generation/prompts.py`, `backend/app/generation/router.py`

## What it does

Takes a user's question, runs it through the full pipeline (rewrite → route → retrieve → rerank → draft → refuse-or-answer), and streams the result back over Server-Sent Events via `POST /chat`. `generator.py`'s `generate_answer()` is the one place that wires every other stage's function together in order — it's the "conductor" of the whole system. Answers are only written from the actual retrieved passages, with the model told never to guess, matching the project's core rule that a confidently wrong answer is worse than no answer.

## Example

**Input:** a POST to `/chat` with `{"query": "can I carry forward unused leave?", "tenant_id": "..."}`
**Output:** a stream of SSE events — zero or more `token` events (the answer typed out live), then one `final` event with the answer text, a list of citations (chunk id, document id, section path), a confidence score, and `refused: false`. If nothing relevant was found, the stream is just one `final` event with `refused: true`, `answer: ""`, and a reason.

## Depends on / called by

Required (Priority 1) dependencies, called directly: P2's `retrieve_chunks()` (Stage 3, dense retrieval), P3's `embed_text()` (turns the question into a search vector), P5's `decide_refusal()` (decides whether to answer or refuse). Optional (Priority 2) dependencies, called only if available and safely skipped otherwise: P4's own `query_rewriter.rewrite()`, P2's `route_query()` and `hybrid_retrieve_chunks()`, P3's `rerank()`. Called by `router.py`'s `POST /chat` endpoint, which is what the frontend (P7) actually talks to.

## Fallback behavior

N/A — Priority 1, this is the spine of the whole system. It's the file that provides the fallback behavior for every Priority 2 feature it calls (if query rewriting, routing, hybrid search, or reranking aren't ready yet or fail, this file quietly falls back to the simpler Priority 1 version of each step instead of crashing the request).

## Status

Done. Verified with 6 automated tests, all passing (see `backend/tests/test_generation.py`) — covers zero-result refusal without a wasted AI call, a good match producing a cited answer, a low-confidence match refusing correctly, a vague question triggering a clarifying question, an unexpected error still returning a clean response instead of breaking the connection, and correct merging when a question gets split into sub-questions.

## Known issues / open questions

A few things flagged for the team rather than silently decided: (1) citations currently show a raw document id instead of a readable document title, because `ChunkResult` doesn't carry a title field yet, even though the `documents` table has one — this needs a small addition on P2's side. (2) The OpenAI key setting in `config.py` is marked optional, but this feature can't work at all without a real one — worth confirming the team's actual key is set before the full demo. (3) There's currently no way for the frontend to send a manual search filter (like "only show HR documents") — `ChatRequest` doesn't have a field for it yet, which would need P2 (schema) and P7 (UI) to add.

## Fix applied during review

`router.py` originally trusted whatever `tenant_id` was in the request body directly, without checking it against the logged-in user's actual tenant. That meant a request could technically claim a different tenant's id and pull that tenant's data — a real gap against the project's tenant isolation rule (Section 1). Fixed by always using the tenant_id from the verified login (`current_user.tenant_id`) instead, and logging a warning if the two ever don't match.

## Tests

`backend/tests/test_generation.py` — 6 tests, all passing. Uses mocked versions of the retrieval, embedding, and refusal-decision functions (since those other tags' real implementations aren't finished yet), so these tests run and prove the pipeline's own logic today, independent of the rest of the team's progress.