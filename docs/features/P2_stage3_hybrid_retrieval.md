# Stage 3 — Hybrid Retrieval & RRF Fusion

**Owner:** P2  
**Stage:** 3  
**Priority:** 2  
**Files:**
- `backend/app/retrieval/hybrid_retrieval.py`

## What it does

`hybrid_retrieval.py` executes full-text keyword search (BM25) and dense vector retrieval in parallel, and merges both ranked result lists using **Reciprocal Rank Fusion (RRF)**. 

Dense retrieval captures semantic similarities even when phrasing differs, while BM25 catches exact keyword/acronym matches that dense models might rank lower. Fusing them with RRF combines both ranked lists by positional rank rather than uncalibrated raw scores:

$$RRF\_score(d) = \sum_{m \in \{\text{dense}, \text{bm25}\}} \frac{1}{k + r_m(d)}$$

where $k = 60$ is the standard smoothing constant, and $r_m(d)$ is the 1-based rank of chunk $d$ in retrieval list $m$. Chunks appearing in both lists receive a natural score boost.

## Example

**Input:**
```python
from uuid import UUID
from app.retrieval.hybrid_retrieval import hybrid_retrieve
from app.schemas import MetadataFilters

fused_results = await hybrid_retrieve(
    bm25_query="carry forward earned leave",
    query_embedding=[...],  # dense embedding vector from embeddings.embed_text()
    tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
    filters=MetadataFilters(department="HR"),
    top_k=25,
    session=db_session,
    scoped_sections=None,
)
```

**Output:**
```python
# list[ChunkResult] sorted by descending RRF fused score
[
    ChunkResult(
        chunk_id=UUID("..."),
        document_id=UUID("..."),
        text="Employees may carry forward up to 15 days of earned leave...",
        section_path="2.2.2 Carry-forward",
        score=0.032787,  # RRF score (1/61 + 1/61 = 0.032787)
        department="HR",
        doc_type="policy",
        ...
    ),
    ...
]
```

## Depends on / called by

| Direction | Module / function |
|---|---|
| **Calls** | `app.retrieval.dense_retrieval.retrieve_chunks` |
| **Calls** | PostgreSQL `to_tsvector` / `plainto_tsquery` / `ts_rank` |
| **Called by** | P4 `generation/generator.py` (Stage 3 step in full RAG pipeline) |

## Fallback behavior

- If BM25 full-text search returns no results, `hybrid_retrieve` directly returns the dense search results.
- If dense retrieval returns no results, `hybrid_retrieve` returns the BM25 search results.
- If this entire module raises an exception or is unavailable, `generator.py` falls back cleanly to dense-only retrieval (`dense_retrieval.py`).

## Status

Done

## Known issues / open questions

- In PostgreSQL, BM25 uses the `english` text search configuration.
- For in-memory testing or non-Postgres environments, a token frequency keyword matcher serves as the BM25 fallback.

## Tests

`backend/tests/test_retrieval.py`:
- `test_hybrid_retrieval_rrf` (verifies parallel execution, keyword and dense matching, and RRF score calculation)
