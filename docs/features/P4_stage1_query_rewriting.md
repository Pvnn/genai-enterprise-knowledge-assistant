# Query Rewriting

**Owner:** P4
**Stage:** 1
**Priority:** 2
**Files:** `backend/app/generation/query_rewriter.py`, `backend/app/generation/prompts.py` (added `query_rewriter_user()`)

## What it does

Takes the user's raw question and rewrites it into a structured form the rest of the pipeline needs: acronyms expanded using the tenant's glossary (built by P1), extracted search filters (department, doc type, version status), separate phrasings for keyword search vs. meaning-based search, a compound question split into sub-questions if needed, and a flag for when the question is too vague to answer safely without asking the user something back.

## Example

**Input:** `rewrite("can I carry forward my PTO", tenant_id, session)` for a tenant whose glossary has `PTO -> Paid Time Off`
**Output:** a `RewriteResult` with `expanded_query="can I carry forward my Paid Time Off"`, filters guessed from context (e.g. `doc_type="leave_policy"`), a keyword-search phrasing, a meaning-search phrasing, and `needs_clarification=False`.

## Depends on / called by

Depends on P1's `glossary` table (read directly with a database query) and the same LLM used elsewhere in the project (`gpt-4o-mini`). Called by `generator.py`'s `_get_rewrite()` as the Priority 2 path for Stage 1.

## Fallback behavior

Two layers of the same safe fallback. If this whole file isn't available, `generator.py` catches that and just uses the raw question as-is, with no filters and no clarification — the Priority 1 behavior. Separately, even when this file IS available, if the AI's response comes back broken or incomplete, `rewrite()` itself catches that and returns that same safe, raw-question version instead of crashing.

## Status

Done. Verified with 5 automated tests, all passing (see `backend/tests/test_query_rewriter.py`).

## Known issues / open questions

Found and fixed a real bug while building this: `generator.py` was calling this function's arguments in the wrong order (a leftover from before we confirmed the real function signature). Fixed by calling it with named arguments instead of positional ones, so this can't silently happen again.

Also found a mismatch worth telling the team: the AI is instructed to return a `"role"` field (e.g. "student", "staff") as one of the filters, but that field doesn't actually exist in the shared `MetadataFilters` shape — so right now, any role the AI identifies is silently thrown away. Either the instructions should stop asking for it, or P2 should add a `role` field to `MetadataFilters` if it's actually meant to be used for filtering.

## Tests

`backend/tests/test_query_rewriter.py` — 5 tests, all passing: reading glossary entries back correctly, handling a tenant with no glossary yet, a well-formed AI response producing the right structured result, a response containing that unsupported `role` field not breaking anything, and a broken/incomplete AI response safely falling back to the raw question. The AI call is mocked in every test — none of them need a real API key or make a real network call.