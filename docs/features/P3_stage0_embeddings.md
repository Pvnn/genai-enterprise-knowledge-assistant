# Stage 0 — Embeddings & Batch Indexer

**Owner:** P3
**Stage:** 0
**Priority:** 1
**Files:**
- `backend/app/retrieval/embeddings.py`
- `backend/app/retrieval/indexer.py`

## What it does

`embeddings.py` wraps Google Gemini (`gemini-embedding-001`), providing an async interface for single texts (`embed_text(text)`) and batch texts (`embed_batch(texts)`).

### Key Features:
- **Output Dimension**: 768 (`output_dimensionality=768`).
- **Retry Policy**:
  - Transient failures (network errors, timeouts, HTTP 429 rate limits, HTTP 5xx server errors) are retried using binary exponential backoff (`delay = 2**attempt`) up to `Settings.embedding_max_retries` (default: 3).
  - Permanent failures (401 invalid key, 403 forbidden, 400 invalid argument, 404 model not found) are **not** retried and raise immediately.
  - If retries exhaust for transient errors, a typed `EmbeddingError` is raised.

`indexer.py` builds on top of `embeddings.py`: it queries the `chunks` table for any row whose `embedding` column is NULL, calls `embed_batch()` in batches of `embed_batch_size` (default 256), then writes the resulting vectors back as JSON-serialised floats. Both modules are async and pull all configuration exclusively from `app.config.get_settings()`.

## Example

**Input (`embed_text`):**
```python
vector = await embed_text("What is the leave encashment policy?")
# → list[float], length 768
```

**Input (`embed_batch`):**
```python
vectors = await embed_batch(["policy text A", "policy text B", "policy text C"])
# → list[list[float]], length 3, each of length 768
```

**Input (`index_chunks`):**
```python
n = await index_chunks(session=db_session, tenant_id="aaaa-…")
# → int: number of chunks newly embedded, e.g. 142
```

**Output (`index_chunks`):** The `chunks` table rows for that tenant now have `embedding` populated. The function is idempotent — re-running skips already-embedded rows.

## Depends on / called by

| Direction | Module / function |
|-----------|-------------------|
| **Calls** | `google.genai.Client.models.embed_content` (Google Gemini API) |
| **Called by (embed_text)** | P2 `retrieval/dense_retrieval.py :: retrieve_chunks()` — query embedding at retrieval time |
| **Called by (embed_text)** | P2 `retrieval/routing.py` — summary-match embedding |
| **Called by (embed_batch)** | `indexer.py :: index_chunks()` |
| **Called by (index_chunks)** | P1 `ingestion/run_ingestion.py` ingestion pipeline (Stage 0) |

## Error handling & Retry behavior

1. Transient failure → retry with exponential backoff up to `embedding_max_retries` (1s, 2s, 4s...) → raise `EmbeddingError` if retries exhaust.
2. Permanent failure → no retries → raise `EmbeddingError` immediately.
3. Missing API key → raise `EmbeddingConfigurationError`.

## Status

Done

## Known issues / open questions

- `indexer.py` stores embeddings as `json.dumps(vector)` into a `Text` column.
  P2 must run the Alembic migration that converts `chunks.embedding` to
  `vector(768)` on Neon **before** `dense_retrieval.py` can execute pgvector
  ANN queries against it. Until then, indexing populates the column but
  retrieval will not find vectors.
- The Gemini client is cached per-process via `@lru_cache`. In tests, mock
  `app.retrieval.embeddings._get_client` to avoid cache-poisoning across test sessions.

## Tests

`backend/tests/test_embeddings.py` — 17 unit and integration tests covering:
- 768-dimensional outputs
- Batch order alignment
- Transient error retry and exponential backoff
- Permanent error bypass of retries
- Transient retry exhaustion raising typed `EmbeddingError`
- Permanent failure raising typed `EmbeddingError`
- Missing API key raising typed `EmbeddingConfigurationError`
- Input validation (empty text, empty list, empty strings)
- Vector count mismatch detection (guards against silent data loss)
- Dimension mismatch detection
- `embed_text()` delegation contract to `embed_batch()`
- Live integration tests

`backend/tests/test_indexer.py` — 8 unit tests covering:
- Happy path indexing with sequential batching
- Idempotent execution (0 chunks when already embedded)
- Batch chunking (300 chunks with batch size 256 -> 2 batches, 2 commits)
- Invalid non-UUID tenant ID validation before DB access
- Database fetch error handling wrapped in `IndexerError`
- `EmbeddingError` propagation preserving prior committed batch progress
- Vector count vs text count mismatch defense
- Database write failure with transaction rollback
