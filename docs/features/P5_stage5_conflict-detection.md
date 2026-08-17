# Version-Conflict Detection

**Owner:** P5
**Stage:** 5
**Priority:** 2
**Files:** backend/app/generation/conflict_detector.py

## What it does
Detects when two current chunks from different documents give contradictory information regarding the same query context. This prevents the system from silently picking one policy version over another, instead surfacing both to the user for clarification.

## Example
**Input:** `top_chunks` containing two excerpts marked `version_status="current"` from Document A and Document B.
**Output:** `ConflictResult(conflict=True, conflicting_chunks=[chunk_from_A, chunk_from_B])` if the LLM detects a direct contradiction between them.

## Depends on / called by
Calls: `AsyncOpenAI` for LLM contradiction detection.
Called by: P5's `grounding.decide_refusal()`.

## Fallback behavior
If this module is missing, fails, or throws an exception (e.g. LLM API failure), it fails safe by returning `ConflictResult(conflict=False)` and logs the error, allowing the Priority 1 refusal and generation pipeline to proceed normally.

## Status
Done

## Known issues / open questions
The spec signature for `check_conflict` does not take the `query`, so the LLM is prompted to find general contradictions among the retrieved chunks rather than specifically checking against the query. The user confirmed this is the intended approach to strictly follow the Section 6 signature.

## Tests
not yet written
