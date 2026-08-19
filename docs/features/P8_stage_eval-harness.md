# Evaluation Harness

**Owner:** P8  
**Stage:** Eval  
**Priority:** 1  
**Files:** `eval/harness.py`

## What it does

An automated evaluation framework that reads the gold QA set, calls the `/chat` endpoint (or a mock), and computes Hit-Rate@k, MRR, Refusal Accuracy, and Faithfulness. Provides both mock mode (for early testing) and real API mode (for production evaluation). Saves detailed per-question results for analysis.

## Example

**Input:** `python harness.py --gold eval/gold_qa.json --mock --output results.json`
**Output:** Evaluation summary with Hit-Rate@5, Hit-Rate@10, MRR, Refusal Accuracy, and Faithfulness metrics.

## Depends on / called by

- Depends on: P4's `/chat` endpoint (real API mode)
- Called by: The team when evaluating system performance

## Fallback behavior

N/A - Priority 1 work, this is the spine.

## Status

**Done** – Harness fully functional with mock mode; ready for real API integration.

## Known issues / open questions

- Faithfulness evaluation requires OpenAI API key
- Relies on `/chat` endpoint returning `citations` with `document_id` and `section_path`
- Needs coordination with P4 for endpoint URL and response format

## Tests

`tests/test_harness.py` 