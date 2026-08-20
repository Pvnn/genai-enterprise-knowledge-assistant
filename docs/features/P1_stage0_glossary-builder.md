# Stage 0: Glossary Builder

**Priority:** 2
**Owner:** P1

## Overview
The Glossary Builder is responsible for auto-building a corpus-wide acronym and entity glossary during the document ingestion phase. This glossary is later used by Stage 1 query rewriting (Priority 4) to seamlessly expand user acronyms and improve search recall.

## Implementation Details
We implement the glossary extraction using a highly optimized, robust Regex heuristic approach. This bypasses the need for an LLM entirely, saving tokens, time, and entirely avoiding context length limits and JSON-validation errors on large chunks. 

The implementation lives in `backend/app/ingestion/glossary_builder.py`.

### 1. Pattern Matching & Regex Heuristics
The extractor scans document chunks for two primary definition structures:
*   **Full Expansion (ACRONYM)**: e.g., "Maximal Marginal Relevance (MMR)"
    `\b((?:[A-Z][a-z0-9\-]+\s+){1,6}[A-Z][a-z0-9\-]+)\s*\(([A-Z0-9]{2,8})\)`
*   **ACRONYM (Full Expansion)**: e.g., "CRAG (Corrective Retrieval-Augmented Generation)"
    `\b([A-Z0-9]{2,8})\s*\(([A-Z][A-Za-z0-9\-,\s]{5,70})\)`

### 2. Validation Pipeline
Before being inserted into the glossary, candidate matches run through two cleanup functions:
*   `clean_expansion()`: Strips trailing spaces, normalizes whitespace, and drops leading stopwords (e.g., "the ", "using ", "for ").
*   `is_valid_acronym_match()`: 
    *   Verifies acronym length (2–8 characters).
    *   Checks exact initials matching (e.g., extracting the first letter of each significant word).
    *   Checks subsequence alignment (ensures the letters in the acronym appear in order within the initials or expansion, efficiently capturing "HNSW" -> "Hierarchical Navigable Small World").

### 3. Database Persistence
Valid entries are batched and inserted directly into the PostgreSQL `glossary` table using SQLAlchemy in `backend/app/ingestion/run_ingestion.py`.

## Fallback Behavior
If regex validation fails or no acronyms are found, the document simply returns an empty list, and the document is ingested successfully without a glossary, per the engineering spec.
