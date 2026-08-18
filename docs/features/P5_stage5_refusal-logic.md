# Refusal Logic

**Owner:** P5
**Stage:** 5
**Priority:** 1
**Files:** backend/app/generation/grounding.py

## What it does
This feature implements the core refusal logic to prevent hallucination when no relevant information is retrieved. It evaluates the top retrieved chunks and the LLM's self-reported confidence. If no chunks survived the filters, the top score is below the threshold, or the LLM confidence is low, it blocks the answer and returns a safe refusal message.

## Example
**Input:** `top_chunks` is empty or the top chunk's score is 0.65.
**Output:** `RefusalDecision(refused=True, reason="I couldn't find a passage in the current policy documents that directly answers this...", confidence=0.0, conflict=False)`

## Depends on / called by
Calls: `AsyncOpenAI` for LLM confidence rating. Also calls P5's `conflict_detector.check_conflict()`.
Called by: P4's `generation/generator.py`.

## Fallback behavior
N/A — no fallback, this is the spine.

## Status
Done

## Known issues / open questions
The spec required asking the LLM for high/medium/low confidence, but `schemas.py` defines `confidence` as a float. I have mapped the LLM's text output to floats (high=1.0, medium=0.5, low=0.0).

## Tests
`backend/tests/test_grounding.py`

