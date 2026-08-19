# Neon Object Storage

**Owner:** P1
**Stage:** 0
**Priority:** 1
**Files:** `backend/app/ingestion/storage.py`

## What it does

It provides utility functions (`upload_markdown` and `get_markdown`) to interface with Neon's S3-compatible Object Storage. During the ingestion pipeline, the fully parsed markdown of the document is uploaded to the storage backend. This provides a durable, exact-match text representation of the document for NotebookLM-style citations on the frontend, separated from the database.

## Example

**Input:** Object key (e.g. `markdowns/123e4567-e89b-12d3-a456-426614174000.md`) and raw Markdown string.
**Output:** The markdown is stored in the Neon Object Storage bucket, and its content can be dynamically retrieved at any time.

## Depends on / called by

Depends on: `boto3` (configured with Neon endpoint URLs and credentials).
Called by: `run_ingestion.py` (to upload during parsing) and `router.py` (via `GET /documents/{document_id}/content` to retrieve for the frontend).

## Fallback behavior

If Neon object storage is unavailable or credentials are missing/invalid, `upload_markdown` logs a warning and aborts gracefully without failing the ingestion pipeline. However, citations to the source document content on the frontend will be unavailable for that specific document.

## Status

Done

## Known issues / open questions

The bucket name is automatically discovered from the connection credentials. If a project has multiple buckets, it will silently use the first one returned.

## Tests

End-to-End verified using the `test_e2e_api.py` and `check_neon.py` scripts against the live Neon Postgres Branch Storage feature.
