# Stage 4 — Cross-Encoder Reranker

**Owner:** P3
**Stage:** 4
**Priority:** 2
**Files:**
- `backend/app/retrieval/reranker.py`

## What it does

After hybrid retrieval returns ~25 candidate chunks, `reranker.py` applies
a `bge-reranker-base` cross-encoder (via `FlagEmbedding`) to jointly score
every `(query, chunk_text)` pair and re-sort the list by descending relevance
score. The top `n` chunks (default 5, from `Settings.reranker_top_n`) are
returned to the generator. The model runs CPU-only — no GPU is required.

## Example

**Input:**
```python
from app.retrieval.reranker import rerank

top5 = rerank(
    query="What is the maternity leave policy?",
    chunks=retrieved_25_chunks,   # list[ChunkResult] from hybrid retrieval
    top_n=5,
)
```

**Output:**
```python
# list[ChunkResult], length 5, sorted by cross-encoder score descending
[ChunkResult(chunk_id=…, text="Maternity leave is 26 weeks…", score=0.97, …), …]
```

## Depends on / called by

| Direction | Module / function |
|-----------|-------------------|
| **Calls** | `FlagEmbedding.FlagReranker.compute_score()` (BAAI/bge-reranker-base) |
| **Called by** | P4 `generation/generator.py` — after hybrid retrieval returns ~25 candidates |

## Fallback behavior

`rerank()` is fully fail-safe. If `FlagEmbedding` is not installed, the model
fails to download, or `compute_score()` raises for any reason, the function:

1. Logs a `WARNING` with the exception detail.
2. Returns `chunks[:top_n]` in the original retrieval order — no exception
   propagates to the caller.

This matches P4's documented fallback: "if reranker is not available, take the
first 5 as-is". The `_model_load_failed` flag prevents repeated heavyweight
load attempts after a confirmed failure.

## Status

Done

## Known issues / open questions

- `ChunkResult` field names (`chunk_id`, `document_id`, `text`, `section_path`,
  `score`) must be confirmed with P2 before integration — if `schemas.py` uses
  different names the import will break at runtime.
- First call to `rerank()` triggers a one-time model download from HuggingFace
  Hub (~1 GB). In production, pre-download the model during Docker image build
  with `python -c "from FlagEmbedding import FlagReranker; FlagReranker('BAAI/bge-reranker-base')"`.
- The module-level model cache (`_reranker_model`) is process-scoped.
  In multi-worker deployments (e.g. `uvicorn --workers 4`) each worker loads
  its own copy, multiplying RAM usage. Pin to a single worker or use a shared
  model server if memory is constrained.
- `normalize=True` is passed to `compute_score()` so scores fall in [0, 1].
  If P4 needs raw logits for calibration, this can be toggled via a Settings
  flag.
- `rerank()` is synchronous (not `async`). P4 should call it in a
  `loop.run_in_executor(None, rerank, …)` if it needs to avoid blocking the
  asyncio event loop during scoring of large batches.

## Tests

`backend/tests/test_reranker.py` — 10 tests (happy path, boundary cases,
three distinct fallback paths: model load failure flag, `ImportError`,
`compute_score` exception, unexpected `_load_model` exception, dynamic `Settings.reranker_top_n` fallback,
settings failure fallback, and invalid/negative `top_n` clamping)


