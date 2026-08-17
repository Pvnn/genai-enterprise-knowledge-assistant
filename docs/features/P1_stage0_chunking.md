# Heading-aware Chunking

**Owner:** P1
**Stage:** 0
**Priority:** 1
**Files:** `backend/app/ingestion/chunker.py`

## What it does

It takes the structured Markdown output from the OCR phase and splits it into logical chunks of roughly ~1,200 characters each. Crucially, it preserves the `section_path` (e.g., "Heading 1 / Subheading 2") for each chunk instead of splitting mid-clause or losing track of the document's structure.

## Example

**Input:** Markdown string from the Docling output.
**Output:** A list of chunk objects, such as `{"text": "...", "section_path": "UNIVERSITY GRANTS COMMISSION BAHADUR SHAH ZAFAR MARG NEW DELHI"}`.

## Depends on / called by

Depends on: None
Called by: `run_ingestion.py`

## Fallback behavior

N/A — no fallback, this is the spine.

## Status

Done

## Known issues / open questions

The chunking size is currently hardcoded to roughly 1200 characters target length. It might need to be fine-tuned when testing the retrieval system in production.

## Tests

Not yet written (`tests/test_ingestion.py` stub to be written).
