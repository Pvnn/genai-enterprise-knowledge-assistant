# Evaluation Harness & Failure Attribution Report

**Owner:** P8
**Stage:** 5 / Eval
**Priority:** 2
**Files:** backend/app/eval/harness.py, backend/app/eval/report.py, backend/app/eval/run_eval.py

## What it does
Scores the RAG system against gold questions for hit-rate@k, faithfulness, and hallucination rates. Generates an ablation failure-attribution report breaking errors down by Stage 2 (Routing), Stage 3 (Retrieval), and Stage 5 (Generation).

## Example
**Input:** Gold question list evaluated across pipeline stages.
**Output:** Dictionary with summary metrics and `stage_breakdown` (routing, retrieval, generation error counts).

## Depends on / called by
Depends on `gold_set.py`. Reports results to CLI runner `run_eval.py`.

## Fallback behavior
If downstream live endpoints are unavailable during development, falls back to standalone mock evaluation.

## Status
Done

## Known issues / open questions
Refusal threshold calibrated. Live integration ready once P4 `/chat` endpoint is connected.

## Tests
eval/tests/test_harness.py (14 passed)