# Stage 0 — Embeddings & Batch Indexer

**Owner:** P3
**Stage:** 0
**Priority:** 1
**Files:**
- `backend/app/retrieval/embeddings.py`
- `backend/app/retrieval/indexer.py`

## What it does

`embeddings.py` wraps the OpenAI `text-embedding-3-small` API, exposing
`embed_text(text)` for single strings and `embed_batch(texts)` for
bulk calls. `indexer.py` builds on top of it: it queries the `chunks`
table for any row whose `embedding` column is NULL, calls `embed_batch()`
in batches of 256, then writes the resulting vectors back as JSON-serialised
floats. Both functions are async and pull all configuration exclusively from
`app.config.get_settings()`.

## Example

**Input (`embed_text`):**
```python
vector = await embed_text("What is the leave encashment policy?")
# → list[float], length 1536
```

**Input (`embed_batch`):**
```python
vectors = await embed_batch(["policy text A", "policy text B", "policy text C"])
# → list[list[float]], length 3, each of length 1536
```

**Input (`index_chunks`):**
```python
n = await index_chunks(session=db_session, tenant_id="aaaa-…")
# → int: number of chunks newly embedded, e.g. 142
```

**Output (`index_chunks`):** The `chunks` table rows for that tenant now
have `embedding` populated. The function is idempotent — re-running skips
already-embedded rows.

## Depends on / called by

| Direction | Module / function |
|-----------|-------------------|
| **Calls** | `openai.AsyncOpenAI.embeddings.create` (via `embeddings.py`) |
| **Called by (embed_text)** | P2 `retrieval/dense_retrieval.py :: retrieve_chunks()` — query embedding at retrieval time |
| **Called by (embed_text)** | P2 `retrieval/routing.py` — summary-match embedding |
| **Called by (embed_batch)** | `indexer.py :: index_chunks()` |
| **Called by (index_chunks)** | P1 `ingestion/run_ingestion.py` ingestion pipeline (Stage 0) |

## Fallback behavior

N/A — no fallback. This is the spine of both the ingestion pipeline and
dense retrieval. If the OpenAI embeddings API is unavailable, `EmbeddingError`
is raised, the ingestion job fails and must be retried. No silent degradation.

## Status

Done

## Known issues / open questions

- `indexer.py` stores embeddings as `json.dumps(vector)` into a `Text` column.
  P2 must run the Alembic migration that converts `chunks.embedding` to
  `vector(1536)` on Neon **before** `dense_retrieval.py` can execute pgvector
  ANN queries against it. Until then, indexing populates the column but
  retrieval will not find vectors.
- The OpenAI client is cached per-process via `@lru_cache`. In tests, mock
  `app.retrieval.embeddings._get_client` rather than the `AsyncOpenAI`
  constructor to avoid cache-poisoning across test sessions.
- `EMBED_BATCH_SIZE = 256` is hardcoded. If OpenAI raises a payload-size error,
  P3 should lower this or make it a `Settings` field.
- `embed_batch` does not retry on transient rate-limit errors. If the ingestion
  pipeline sees frequent 429s, add exponential back-off before the
  `client.embeddings.create` call.

## Tests

`backend/tests/test_embeddings.py` — 8 tests (embed_text, embed_batch, error paths)
`backend/tests/test_indexer.py`    — 7 tests (happy path, idempotent, batching,
                                     invalid UUID, DB fetch failure,
                                     EmbeddingError propagation, DB write failure)

## Coding conventions (all followed)

- `snake_case` functions/variables, `PascalCase` classes (`EmbeddingError`,
  `IndexerError`), `UPPER_SNAKE_CASE` constants (`EMBED_BATCH_SIZE`).
- Google-style docstrings on every public function.
- `logging.getLogger(__name__)` — no `print()`.
- Absolute imports rooted at `app` (`from app.config import get_settings`,
  `from app.retrieval.embeddings import embed_batch`).
- `black`-formatted (4-space indent, double quotes, trailing commas).
