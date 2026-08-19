# Stage 0: Ingestion Endpoints (Router)

**Priority:** 1 & 2
**Owner:** P1
**Files:** `backend/app/routers/ingestion.py`

## Overview
The Ingestion Router exposes the REST API endpoints required by the frontend to upload documents and track their processing status. It bridges the gap between the user interface and the background ingestion orchestrator.

## Implementation Details

### `POST /documents/upload`
Accepts a `multipart/form-data` request containing the document file, alongside required metadata (`department`, `doc_type`).
* **Security:** Gated to admin users only (utilizing the shared `get_current_user` dependency from P6/P2).
* **Workflow:** 
  1. Inserts a new `pending` record into the `documents` table to reserve a `document_id`.
  2. Saves the uploaded file to a temporary staging path.
  3. Dispatches the `ingest_document` pipeline as a FastAPI `BackgroundTask`, ensuring the HTTP request returns immediately rather than blocking on OCR/embeddings.
* **Returns:** `{ "document_id": UUID, "ingestion_status": "pending" }` (HTTP 202 Accepted).

### `GET /documents/{document_id}/status`
Allows the client to poll the processing status of a previously uploaded document.
* **Returns:** The current state of the document. E.g., `{ "document_id": UUID, "ingestion_status": "done", "error_detail": null }`.

## Fallback Behavior
If the upload fails synchronously (e.g., invalid payload or database constraint error), an HTTP 400 or 500 is returned immediately. If the background pipeline fails, the document's `ingestion_status` transitions to `failed`, and `error_detail` is populated, which the client learns upon its next polling request.
