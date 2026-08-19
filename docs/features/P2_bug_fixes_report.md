# P2 Bug Fixes & Improvements Report

**Owner:** P2  
**Date:** August 19, 2026  
**Reference Document:** `docs/spec/full_pipeline_test_report.md`  
**Status:** Completed & Verified  

---

## 1. Overview & Objectives

During end-to-end integration testing documented in `full_pipeline_test_report.md`, `POST /chat` could not execute vector similarity search over enterprise documents. Two main issues were identified under P2's ownership:

1. **`chunks.embedding` column type mismatch**: The column remained as `Text` rather than `vector(768)` in the live PostgreSQL database, and the base migration still referenced OpenAI's old 1536-dimension vectors.
2. **Missing `session.rollback()` before fallback execution**: When the native pgvector query encountered an error on PostgreSQL, the connection was left in an aborted transaction state, causing subsequent fallback queries to fail with `InFailedSQLTransactionError`.
3. **SQLAlchemy text bind parameter syntax bug**: In `dense_retrieval.py`, using `:vector_str::vector` caused SQLAlchemy's text parser to treat the adjacent colon as an invalid parameter token, failing to bind the parameter and triggering a PostgreSQL syntax error.

All issues have been resolved, verified with unit tests, and validated live against the Neon PostgreSQL database.

---

## 2. Detailed Summary of Changes

### A. Base Migration Schema (`backend/db/migrations/versions/a1b2c3d4e5f6_initial_schema.py`)
- **Updated Comments & Docstrings**: Changed vector dimension references from `vector(1536)` (OpenAI) to `vector(768)` (Google Gemini `gemini-embedding-001`).
- **Automatic pgvector Setup on PostgreSQL**: Added a dialect check in `upgrade()` so that when running against PostgreSQL/Neon, `CREATE EXTENSION IF NOT EXISTS vector;` is executed and `chunks.embedding` is automatically altered from `Text` to `vector(768) USING embedding::vector;`. On SQLite (in-memory test runners), it remains `Text`.
- **Live Database Update**: Altered `chunks.embedding` on the shared Neon PostgreSQL database to `vector(768)` containing all 34 pre-indexed document chunks.

### B. Dense Retrieval (`backend/app/retrieval/dense_retrieval.py`)
- **Fixed SQL Cast Syntax**: Replaced `1 - (c.embedding::vector <=> :vector_str::vector)` with `1 - (c.embedding <=> CAST(:vector_str AS vector))` so SQLAlchemy properly binds `:vector_str` as a query parameter.
- **Added Transaction Rollback on Failure**: In `retrieve_chunks()`, wrapped the fallback call with `await session.rollback()` inside the `except Exception` block, ensuring clean recovery from aborted PostgreSQL transactions.
- **Robust Fallback Deserialization**: Extended `_retrieve_fallback()` to handle JSON strings, python lists, numpy arrays, and vector sequences.

### C. Hybrid Retrieval (`backend/app/retrieval/hybrid_retrieval.py`)
- **Added Transaction Rollback on Failure**: In `_search_bm25()`, added `await session.rollback()` when `_search_bm25_postgres()` fails before delegating to `_search_bm25_fallback()`.

### D. Unit Tests (`backend/tests/test_retrieval.py`)
- **Added Fallback & Rollback Test**: Added `test_dense_retrieval_fallback_on_pgvector_error` to verify that when `_retrieve_pgvector` raises an exception, `retrieve_chunks` invokes `session.rollback()` and successfully returns fallback results.
- **Maintained Shared SQLite Fixtures**: Preserved `session.flush()` in `_seed_test_data()` for compatibility with `conftest.py` transaction rollback teardown.

---

## 3. Code Modifications (Diffs)

### `backend/db/migrations/versions/a1b2c3d4e5f6_initial_schema.py`
```diff
-  - pgvector's `vector` type is used for chunks.embedding; the pgvector
-    extension must be enabled before running this migration:
-      CREATE EXTENSION IF NOT EXISTS vector;
+  - pgvector's `vector(768)` type is used for chunks.embedding (Gemini embeddings).
+    On PostgreSQL / Neon, the pgvector extension is enabled and the column is
+    altered to vector(768). On SQLite (in-memory tests), it remains Text.
...
-        # embedding column: vector(1536) for text-embedding-3-small.
-        # Requires pgvector extension. Added as plain Text here so the migration
-        # runs on SQLite in tests; P3 should ALTER to vector(1536) on Neon.
-        sa.Column("embedding", sa.Text(), nullable=True, comment="pgvector vector(1536)"),
+        # embedding column: vector(768) for gemini-embedding-001.
+        # Added as plain Text here so the migration runs on SQLite in tests;
+        # altered to vector(768) on PostgreSQL below.
+        sa.Column("embedding", sa.Text(), nullable=True, comment="pgvector vector(768)"),
...
+    bind = op.get_bind()
+    if bind and bind.dialect.name == "postgresql":
+        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
+        op.execute("ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(768) USING embedding::vector;")
```

### `backend/app/retrieval/dense_retrieval.py`
```diff
         except Exception as exc:
             logger.warning(
                 "pgvector query failed, falling back to python cosine similarity: %s",
                 exc,
             )
+            try:
+                await session.rollback()
+            except Exception as rb_exc:
+                logger.debug("Session rollback failed or already inactive: %s", rb_exc)

...
         query_sql = f"""
             SELECT 
                 c.id AS chunk_id,
                 c.document_id,
                 c.text,
                 c.section_path,
                 c.department,
                 c.doc_type,
                 c.effective_date,
                 c.version_status,
                 d.source_path,
-                1 - (c.embedding::vector <=> :vector_str::vector) AS score
+                1 - (c.embedding <=> CAST(:vector_str AS vector)) AS score
             FROM chunks c
             LEFT JOIN documents d ON c.document_id = d.id
             WHERE {' AND '.join(where_clauses)}
             ORDER BY score DESC
             LIMIT :top_k
         """
...
         if isinstance(embedding_raw, str):
             try:
                 emb_list = json.loads(embedding_raw)
             except Exception:
                 continue
         elif isinstance(embedding_raw, list):
             emb_list = embedding_raw
+        elif hasattr(embedding_raw, "tolist"):
+            emb_list = embedding_raw.tolist()
+        elif hasattr(embedding_raw, "__iter__"):
+            emb_list = list(embedding_raw)
         else:
             continue
```

### `backend/app/retrieval/hybrid_retrieval.py`
```diff
         except Exception as exc:
             logger.warning("Postgres tsvector search failed, falling back: %s", exc)
+            try:
+                await session.rollback()
+            except Exception as rb_exc:
+                logger.debug("Session rollback failed or already inactive: %s", rb_exc)
```

### `backend/tests/test_retrieval.py`
```diff
+@pytest.mark.asyncio
+async def test_dense_retrieval_fallback_on_pgvector_error(db_session: AsyncSession) -> None:
+    """Verify retrieve_chunks rolls back and recovers via fallback if pgvector query raises."""
+    await _seed_test_data(db_session)
+
+    query_vec = [1.0, 0.0, 0.0] + [0.0] * 765
+    filters = MetadataFilters()
+
+    with patch.object(db_session.bind.dialect, "name", "postgresql", create=True):
+        with patch("app.retrieval.dense_retrieval._retrieve_pgvector", side_effect=RuntimeError("simulated pgvector crash")):
+            with patch("app.retrieval.dense_retrieval._retrieve_fallback", new_callable=AsyncMock) as mock_fallback:
+                mock_fallback.return_value = [
+                    ChunkResult(
+                        chunk_id=uuid4(),
+                        document_id=DOC_UUID,
+                        text="Employees may carry forward up to 15 days of earned leave each calendar year.",
+                        section_path="2.2.2 Carry-forward",
+                        score=0.99,
+                    )
+                ]
+                with patch.object(db_session, "rollback", wraps=db_session.rollback) as mock_rollback:
+                    results = await retrieve_chunks(
+                        query_embedding=query_vec,
+                        tenant_id=TENANT_UUID,
+                        filters=filters,
+                        top_k=10,
+                        session=db_session,
+                    )
+
+                    mock_rollback.assert_awaited_once()
+                    mock_fallback.assert_awaited_once()
+                    assert len(results) == 1
+                    assert "carry forward" in results[0].text
```

---

## 4. Verification & Test Results

### Automated Test Suite
Ran all test suites for retrieval, embeddings, indexer, generation, conflict detection, and grounding:
```bash
pytest backend/tests/test_retrieval.py backend/tests/test_embeddings.py backend/tests/test_indexer.py backend/tests/test_generation.py backend/tests/test_conflict_detector.py backend/tests/test_grounding.py
```
**Output:**
```
============================= test session starts =============================
platform win32 -- Python 3.10.6, pytest-9.1.1, pluggy-1.6.0
collected 43 items

backend\tests\test_retrieval.py .......                                  [ 16%]
backend\tests\test_embeddings.py ...........                             [ 41%]
backend\tests\test_indexer.py .......                                    [ 58%]
backend\tests\test_generation.py ......                                  [ 72%]
backend\tests\test_conflict_detector.py ......                           [ 86%]
backend\tests\test_grounding.py ......                                   [100%]

============================= 43 passed in 5.39s ==============================
```

### Live Database & API Verification
Executed live integration against Neon PostgreSQL (`vector(768)`) and Gemini API:
- `POST /retrieve`: Query *"What is the fee structure for PG first year 2025-2026?"* successfully returned 5 relevant chunks using native pgvector cosine search `<=>`, with the top chunk scoring `0.8166` (`6. P.G 1 ST YEAR FEE STRUCTURE FOR THE SESSION 2025-2026`).
- `POST /chat`: Executed end-to-end through query rewriting, coarse routing, dense retrieval, reranking, and grounding.
