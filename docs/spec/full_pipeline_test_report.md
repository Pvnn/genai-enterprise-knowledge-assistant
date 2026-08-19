# Full Pipeline Test Report

**Tested by:** P4
**Date:** August 19, 2026
**Branch:** `master` (after all teams' PRs merged)
**Environment:** Local machine, real shared Neon database, real Gemini + Groq (OpenAI-compatible) keys

## What this test was

After everyone merged their work into `master`, the goal was to run the actual app end-to-end for the first time — start the real server, log in as a real user, and ask it a real question — to see how far a real request gets through the whole system, and find any integration problems before the demo.

## Setup steps completed

- Pulled `master` with everyone's merged code.
- Installed all dependencies (`pip install -r requirements.txt` + `requirements-dev.txt`).
- Added real `DATABASE_URL` (Neon), `GEMINI_API_KEY`, and a working OpenAI-compatible key (Groq, model `llama-3.3-70b-versatile`) to `.env`.
- Ran `alembic upgrade head` — confirmed the shared database is already at the latest migration (`a1b2c3d4e5f6`), no changes needed.
- Started the real server: `uvicorn app.main:app --reload` — started cleanly with no import errors, confirming every teammate's file loads correctly together.
- Created one test company and one test user directly in the database (no signup endpoint exists yet) to be able to log in.

## What worked

| Test | What it checks | Result |
|---|---|---|
| Server startup | Every file from all 8 people imports and the app boots | **Pass** |
| `POST /auth/login` | Real login with email/password/company name, returns a signed token | **Pass** |
| `GET /auth/me` | Token correctly identifies the logged-in user | **Pass** |
| `POST /chat` (request itself) | Endpoint is reachable, requires login, doesn't crash unhandled | **Pass** — request completed and returned a clean response, not a server crash |

## What failed

**`POST /chat` could not actually search for matching documents.** The request completed (no crash, no dropped connection — it correctly returned a safe `refused: true, refusal_reason: "internal_error"` response instead of failing silently), but the underlying document search itself is broken. Two separate causes were found:

### Bug 1 — `chunks.embedding` column is still plain text, not a real vector type

**Owner: P2** (`backend/db/migrations/versions/a1b2c3d4e5f6_initial_schema.py`, `backend/app/retrieval/dense_retrieval.py`)

The migration file itself documents that this column should be manually changed to a real pgvector `vector` type on the live Neon database (it's left as `Text` in the migration so automated tests can run without pgvector). Checked directly in the database — confirmed it is still `text`, not `vector`. This blocks real similarity search.

**Also:** the migration's comment says the column should be sized for `1536` (OpenAI's old embedding model). The project has since switched to Gemini embeddings, which produce vectors of size `768`. Whoever fixes this needs to use `768`, not the `1536` in the old comment.

### Bug 2 — missing rollback before the retrieval fallback retries

**Owner: P2** (`backend/app/retrieval/dense_retrieval.py`)

`retrieve_chunks()` tries a fast pgvector search first; if that fails, it's supposed to fall back to a simpler backup search on the same database session. But it doesn't call `session.rollback()` between the two attempts. Once the first attempt fails, the database refuses to run anything else on that same connection until it's told to reset — so the backup attempt fails too, with a different, confusing error (`InFailedSQLTransactionError: current transaction is aborted`), even though the backup method itself may be fine.

**Confirmed pgvector extension IS enabled** on the database (version 0.8.6) — ruled that out as a cause.

## Not yet tested

- **Document upload (`POST /documents/upload`)** — not attempted. Testing this wouldn't have added useful information yet, since even a successful upload can't be searched until Bug 1 is fixed. Worth trying once the column type is corrected.
- **Query rewriting and reranking (Priority 2 features)** — not reached, since the request failed before getting that far.

## Suggested next steps

1. P2: change `chunks.embedding` to a real `vector(768)` column on the shared Neon database, and add `session.rollback()` in `dense_retrieval.py` before the fallback query runs.
2. Once fixed, re-run this same test (`POST /chat` with the test login) to confirm retrieval works.
3. Test document upload end-to-end (P1's ingestion pipeline) once retrieval is confirmed working.
