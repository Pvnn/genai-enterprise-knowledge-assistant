# Loader

**Owner:** P1
**Stage:** 0
**Priority:** 1
**Files:** `backend/app/ingestion/loader.py`

## What it does

It takes the securely validated `ChunkDB` objects and commits them to the database. It is responsible for orchestrating the embedding generation (via P3's `embed_batch`) and executing the bulk insert into the `chunks` table. It uses a raw parameterized SQL query to ensure standard Postgres functions like `to_tsvector` (for BM25 text search) can be computed seamlessly on insert. 

## Example

**Input:** `[ChunkDB(id=UUID, document_id=UUID, ...)]` and an open `AsyncSession`.
**Output:** Generates `[0.013, -0.015, ...]` pgvector embeddings and inserts rows into `chunks` table. Returns `None`.

## Depends on / called by

Depends on: `app.retrieval.embeddings.embed_batch` (P3)
Called by: `run_ingestion.py`

## Fallback behavior

N/A — no fallback, this is the spine.

## Status

Done

## Known issues / open questions

None. The `embed_batch` from P3 is fully integrated and tested. The `source_path` attribute was successfully removed from the `chunks` table insertion query because the DB schema from P2 correctly stores it solely in the parent `documents` table.

## Tests

Tested via `backend/test_full_pipeline.py` (live DB insertion and embedding verification).
