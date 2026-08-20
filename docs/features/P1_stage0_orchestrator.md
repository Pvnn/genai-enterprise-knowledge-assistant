# Ingestion Pipeline Orchestrator

**Owner:** P1
**Stage:** 0
**Priority:** 1
**Files:** `backend/app/ingestion/run_ingestion.py`

## What it does

It is the master controller for the entire document ingestion process (Stage 0). It safely manages the database transaction lifecycle for a document upload, orchestrating the transition from a raw PDF file into embedded, searchable database chunks. 

Specifically, it:
1. Updates the `documents` table row to `ingestion_status = 'processing'`.
2. Invokes `parse_document` (OCR).
3. Invokes `chunk_document` (Heading-aware chunking).
4. Invokes `tag_chunks` (Pydantic validation and metadata enrichment).
5. Invokes `load_chunks` (Batch embeddings and pgvector DB insert).
6. Updates the `documents` table row to `ingestion_status = 'done'`, or `'failed'` if any step raises an exception.

## Example

**Input:** `ingest_document("path/to/doc.pdf", document_id=UUID, tenant_id=UUID, ...)`
**Output:** Database is populated with `chunks` linked to the `documents` row, and the pipeline completes cleanly.

## Depends on / called by

Depends on: `ocr.py`, `chunker.py`, `metadata_tagger.py`, `loader.py`
Called by: `app/routers/ingestion.py` (via a FastAPI BackgroundTask) and local batch ingestion scripts.

## Fallback behavior

If an exception occurs anywhere in the pipeline (e.g. Docling crashes, or the database connection drops), the Orchestrator intercepts it, rolls back any partial inserts to the `chunks` table, and sets the parent document's `ingestion_status` to `'failed'`.

## Status

Done

## Known issues / open questions

None. The orchestrator now instantiates its own `AsyncSessionLocal` so it operates correctly in a FastAPI BackgroundTask without losing the DB connection when the HTTP request closes. It also automatically defaults missing `version_status` to `"current"`.

## Tests

`backend/tests/test_ingestion.py` (Unit tests with SQLite pass)
`backend/test_full_pipeline.py` (End-to-end live Neon DB test passes)
