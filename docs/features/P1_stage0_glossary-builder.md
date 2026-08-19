# Acronym & Entity Glossary Builder

**Owner:** P1
**Stage:** 0
**Priority:** 2
**Files:** `backend/app/ingestion/glossary_builder.py`

## What it does

It auto-builds a corpus-wide acronym and entity glossary from the document's chunks using the configured LLM. The extracted terms and expansions are stored in the `glossary` table, scoped by `tenant_id`. This glossary is later used by Stage 1 query rewriting (P4) to expand acronyms in user questions before searching, improving dense retrieval accuracy.

## Example

**Input:** "The students of Undergraduate Courses of DDCE will report to the HoD."
**Output:** `[{"term": "DDCE", "expansion": "Directorate of Distance and Continuing Education"}, {"term": "HoD", "expansion": "Head of Department"}]`

## Depends on / called by

- Called by: `run_ingestion.py` after chunks are built and tagged.
- Depends on: `OpenAI`/LLM configuration to process text and extract structured JSON.

## Fallback behavior

If `glossary_builder.py` is unavailable or fails (e.g., LLM context limits, JSON parsing failure, missing API key), the exception is caught and logged. The `run_ingestion.py` pipeline skips inserting new terms. Stage 1 rewriting simply skips acronym expansion if the table is empty.

## Status

Done

## Known issues / open questions

If a document's total chunk size exceeds the context limit of the LLM, the text is truncated to the first 100,000 characters to prevent token limit errors during extraction.

## Tests

`backend/tests/test_ingestion.py`
