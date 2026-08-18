# Gold QA Set

**Owner:** P8  
**Stage:** Eval  
**Priority:** 1  
**Files:** `eval/gold_qa.json`

## What it does

A comprehensive gold standard Q&A dataset with 335 questions covering 6 Cognizant policy documents. Includes 215 factual questions with ground-truth answers and 120 refusal questions (out-of-scope topics). Used to evaluate the RAG pipeline's retrieval accuracy, generation faithfulness, and refusal correctness.

## Example

**Input:** `python harness.py --gold eval/gold_qa.json --mock`
**Output:** Evaluation summary with Hit-Rate@5, Hit-Rate@10, MRR, and Refusal Accuracy.

## Depends on / called by

- Depends on: None (created manually from policy PDFs)
- Called by: P8's `harness.py`

## Fallback behavior

N/A - Priority 1 work, this is the spine.

## Status

**Done** – 335 questions created and validated.

## Known issues / open questions

- Document IDs are currently filename-based; will need to map to actual database UUIDs once P1 ingests documents
- Section paths may need adjustment to match P1's section_tree format

## Tests

`tests/test_harness.py` 