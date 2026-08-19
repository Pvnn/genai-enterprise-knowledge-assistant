# Document Summarizer

**Owner:** P1
**Stage:** 0
**Priority:** 2
**Files:** `backend/app/ingestion/summarizer.py`

## What it does

It generates a concise summary (<= 200 words) of the ingested document via the configured LLM (e.g., `gpt-4o-mini` / `gpt-oss-120b`). This populates the `documents.summary` field, which is used by Stage 2a routing to narrow the candidate document set based on semantic content.

## Example

**Input:** Full structured markdown of a 20-page document
**Output:** "This document outlines the PG 1st Year Fee Structure for the 2025-2026 session, including tuition, exam, and miscellaneous fees for standard and foreign students. It also details the fee concession policy for meritorious female students."

## Depends on / called by

- Called by: `run_ingestion.py` after parsing the document.
- Depends on: `OpenAI`/LLM configuration to generate the summary.

## Fallback behavior

If `summarizer.py` is unavailable, or the LLM call fails (e.g. missing API key or timeout), the exception is caught and logged. The `documents.summary` field is left `NULL`, and Stage 2a falls back gracefully to metadata-only filtering without the semantic summary.

## Status

Done

## Known issues / open questions

N/A

## Tests

`backend/tests/test_ingestion.py`
