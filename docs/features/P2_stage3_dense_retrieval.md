# Stage 3 — Dense Retrieval (pgvector)

**Owner:** P2  
**Stage:** 3  
**Priority:** 1  
**Files:**
- `backend/app/retrieval/dense_retrieval.py`

## What it does

`dense_retrieval.py` performs Approximate Nearest Neighbor (ANN) cosine similarity search over `chunks.embedding` using metadata filters and tenant boundaries as hard constraints. When Stage 2 routing outputs `scoped_sections`, the search is strictly narrowed to those `(document_id, section_path)` pairs before scoring chunks.

The module supports:
1. **Production mode (PostgreSQL + pgvector)**: Executes native cosine distance queries using pgvector's `<=>` operator directly on Neon.
2. **Fallback mode (Hermetic SQLite / Memory)**: Deserializes JSON embeddings and calculates pure Python cosine similarity, enabling 100% offline, hermetic unit tests with in-memory SQLite.

## Example

**Input:**
```python
from uuid import UUID
from app.retrieval.dense_retrieval import retrieve_chunks
from app.schemas import MetadataFilters, ScopedSection

results = await retrieve_chunks(
    query_embedding=[0.05, 0.98, ...],  # 768-dim list[float] from embeddings.embed_text()
    tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
    filters=MetadataFilters(department="HR", version_status="current"),
    top_k=25,
    session=db_session,
    scoped_sections=[
        ScopedSection(
            document_id=UUID("33333333-3333-3333-3333-333333333333"),
            section_path="2.2.2 Carry-forward",
        )
    ],
)
```

**Output:**
```python
# list[ChunkResult] sorted by descending cosine similarity score
[
    ChunkResult(
        chunk_id=UUID("..."),
        document_id=UUID("33333333-3333-3333-3333-333333333333"),
        text="Employees may carry forward up to 15 days of earned leave...",
        section_path="2.2.2 Carry-forward",
        score=0.9821,
        department="HR",
        doc_type="policy",
        effective_date="2025-01-01",
        version_status="current",
        source_path="/docs/hr_leave.pdf",
    ),
    ...
]
```

## Depends on / called by

| Direction | Module / function |
|---|---|
| **Calls** | `chunks` table, `documents.source_path` join |
| **Called by** | P2 `retrieval/router.py :: retrieve()` — for `POST /retrieve` API calls |
| **Called by** | P2 `retrieval/hybrid_retrieval.py :: hybrid_retrieve()` — runs in parallel with BM25 |
| **Called by** | P4 `generation/generator.py` — core Stage 3 dense search in the end-to-end RAG pipeline |

## Fallback behavior

If native PostgreSQL pgvector `<=>` operator query throws an exception or runs on an in-memory SQLite database in test environments, `retrieve_chunks()` catches the dialect error and transparently falls back to `_retrieve_fallback()`, computing cosine similarity in Python. If no chunks match the hard metadata filters or tenant ID, an empty list `[]` is safely returned.

## Status

Done

## Known issues / open questions

- `chunks.embedding` is stored as `vector(768)` in Postgres on Neon. In local dev environments, ensure `CREATE EXTENSION IF NOT EXISTS vector;` has been executed on the target database.
- `scoped_sections` matches both exact section paths and child sections using prefix matching (`LIKE 'sec_path%'`).

## Tests

`backend/tests/test_retrieval.py`:
- `test_dense_retrieval_ranking_and_isolation` (verifies top chunk ranking and strict multi-tenant isolation)
- `test_dense_retrieval_metadata_filters` (verifies filtering by department, doc_type, and version_status)
- `test_dense_retrieval_scoped_sections` (verifies narrowing search space to specific section paths)
