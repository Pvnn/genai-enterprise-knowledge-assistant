# Gold Evaluation Dataset

**Owner:** P8
**Stage:** 5 / Eval
**Priority:** 1
**Files:** eval/gold_qa.json, backend/app/eval/gold_set.py

## What it does
Provides a structured gold Q&A benchmark dataset covering factual policy queries and explicit out-of-corpus refusal test cases. Used by the eval harness to score hit-rate@k, faithfulness, and hallucination rates.
Questions : 184 factual + 151 refusal (335 total).

## Example
**Input:** Gold benchmark items with questions, ground-truth answers, expected document_ids, and section paths.
**Output:** Parsed `GoldQuestion` dataclass objects loaded for evaluation.

## Depends on / called by
Called by `backend/app/eval/harness.py` and `backend/app/eval/run_eval.py`.

## Fallback behavior
N/A - no fallback, this is the spine.

## Status
Done

## Known issues / open questions
None. Loaded 335 evaluated question pairs cleanly.

## Tests
eval/tests/test_harness.py