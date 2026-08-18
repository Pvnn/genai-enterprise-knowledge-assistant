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

N/A — no fallback, this is the spine. (Note: Currently gracefully intercepts `NotImplementedError` for P3's embedding wrapper and injects a mocked embedding so development is not blocked.)

## Status

Done

## Known issues / open questions

P3 has not implemented `embed_batch()` yet, so the loader currently inserts zero-filled embeddings as a mock if `NotImplementedError` is caught. It relies on the caller (`run_ingestion.py`) to actually call `await session.commit()`, keeping transaction boundaries safe if later chunking fails.

## Tests

Not yet written (`tests/test_ingestion.py` stub to be written).
