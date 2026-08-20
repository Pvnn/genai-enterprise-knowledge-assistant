# Stage 0: Section Tree Extraction

**Priority:** 2
**Owner:** P1
**Files:** `backend/app/ingestion/section_tree.py`

## Overview
The Section Tree extractor is responsible for generating a structured hierarchical table of contents (`section_tree`) for each ingested document. This metadata is stored in `documents.section_tree` as a JSON array. 

It is a crucial component for Stage 2b routing (P2). After candidate documents are narrowed down, the LLM reads the `section_tree` of each candidate to pinpoint exactly which sections contain the answer, enabling the system to pass only the relevant, scoped chunks to the generator rather than the entire document.

## Implementation Details
The section tree is built purely from the Markdown output produced by the OCR step (`parse_document`). By utilizing a Markdown parsing heuristic (e.g. `markdown-it-py` or regex), the module iterates through the text and extracts heading levels (`#`, `##`, `###`, etc.).

It constructs a nested JSON hierarchy corresponding to the document structure. Each node in the tree includes:
* `title`: The text of the heading.
* `section_path`: A string representing the heading hierarchy (e.g., "3. Overview > 3.1 Architecture").
* `children`: An array of sub-headings.

## Fallback Behavior
If the section tree extraction fails, it raises an exception which is caught cleanly by `run_ingestion.py`. The `documents.section_tree` column remains empty (`[]` or `NULL`), but the ingestion pipeline continues successfully. Retrieval then falls back to full-document chunk matching rather than scoped section-level filtering.
