# Stage 2 — Coarse Routing (Document & Section Narrowing)

**Owner:** P2  
**Stage:** 2  
**Priority:** 2  
**Files:**
- `backend/app/retrieval/routing.py`

## What it does

`routing.py` performs coarse document- and section-level narrowing before passage-level search happens. Rather than searching across all chunks in the entire tenant corpus, Stage 2 answers **"which document, and which section of it"** governs the query.

It operates in two sequential sub-steps:
1. **Stage 2a (Document-Level Candidate Selection)**: Filters `documents` by tenant, compares the rewritten query against candidate documents' high-level summaries and titles, and narrows the candidate set to top 3–5 documents.
2. **Stage 2b (Section-Level Tree Reasoning)**: Traverses each candidate document's `section_tree` (JSON table of contents) and uses LLM reasoning (`gpt-4o-mini` / Gemini) or structural keyword matching to pick 1–3 governing section paths.

## Example

**Input:**
```python
from uuid import UUID
from app.retrieval.routing import route_query

scoped_sections = await route_query(
    rewritten_query="can I carry forward my earned leave to next year",
    tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
    session=db_session,
)
```

**Output:**
```python
# list[dict] with 1 to 3 governing (document_id, section_path) pairs
[
    {
        "document_id": UUID("33333333-3333-3333-3333-333333333333"),
        "section_path": "2.2.2 Carry-forward",
    }
]
```

## Depends on / called by

| Direction | Module / function |
|---|---|
| **Calls** | `documents` table (`summary`, `section_tree`) |
| **Calls** | OpenAI API (`gpt-4o-mini`) / heuristic section matcher |
| **Called by** | P4 `generation/generator.py` (Stage 2 routing step) |

## Fallback behavior

If `routing.py` is unavailable, candidate documents have no `summary`/`section_tree` populated, or the LLM call fails, `route_query()` returns an empty list `[]`. In `generator.py`, an empty list translates to `scoped_sections = None`, which cleanly falls back to searching the full metadata-filtered corpus in Stage 3.

## Status

Done

## Known issues / open questions

- Depends on P1 populating `documents.summary` and `documents.section_tree` during the Stage 0 document ingestion pipeline.
- To prevent network latency in offline/test environments, LLM calls enforce a 5-second timeout and validate that API keys are not placeholder strings before connecting.

## Tests

`backend/tests/test_retrieval.py`:
- `test_route_query` (verifies candidate document selection, section tree flattening, and section path matching)
