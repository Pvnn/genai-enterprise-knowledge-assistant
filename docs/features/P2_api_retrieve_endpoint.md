# API Endpoint — POST /retrieve

**Owner:** P2  
**Endpoint:** `POST /retrieve`  
**Priority:** 1  
**Files:**
- `backend/app/retrieval/router.py`

## What it does

`POST /retrieve` is the public HTTP API endpoint for retrieving relevant document chunks given a user query and optional metadata filters.

### Tenant Isolation Guarantee
To prevent multi-tenant data leakage, any `tenant_id` provided in the request body is **strictly overridden** by the authenticated user's `current_user.tenant_id` from the validated JWT bearer token. A caller from Tenant A can never query chunks belonging to Tenant B.

## Contract

**Request (`POST /retrieve`):**
```json
{
  "query": "How many days of leave can I carry forward?",
  "tenant_id": "11111111-1111-1111-1111-111111111111",
  "top_k": 5,
  "filters": {
    "department": "HR",
    "doc_type": "policy",
    "version_status": "current"
  },
  "scoped_sections": [
    {
      "document_id": "33333333-3333-3333-3333-333333333333",
      "section_path": "2.2.2 Carry-forward"
    }
  ]
}
```

**Response (HTTP 200):**
```json
{
  "chunks": [
    {
      "chunk_id": "8f7e2a4d-3b10-4c5e-9a7b-6d4c2e1f8a0b",
      "document_id": "33333333-3333-3333-3333-333333333333",
      "text": "Employees may carry forward up to 15 days of earned leave each calendar year.",
      "section_path": "2.2.2 Carry-forward",
      "score": 0.9821,
      "department": "HR",
      "doc_type": "policy",
      "effective_date": "2025-01-01",
      "version_status": "current",
      "source_path": "/docs/hr_leave.pdf"
    }
  ]
}
```

**Error Response (Shared envelope):**
```json
{
  "error": "internal_server_error",
  "detail": "Failed to generate query embedding: API key expired"
}
```

## Depends on / called by

| Direction | Module / function |
|---|---|
| **Calls** | `app.retrieval.embeddings.embed_text` |
| **Calls** | `app.retrieval.dense_retrieval.retrieve_chunks` |
| **Called by** | Frontend / External API Clients |

## Status

Done

## Tests

`backend/tests/test_retrieval.py`:
- `test_retrieve_api_endpoint` (verifies complete HTTP request/response serialization, embedding generation, and tenant isolation)
