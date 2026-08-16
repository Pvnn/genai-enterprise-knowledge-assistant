# GenAI Enterprise Knowledge Assistant

> **Internal Q&A system over institutional policies, syllabi, circulars, and process documents.**
> Finds the right *passage*, not just the right document — with citations, refusals, and conflict detection.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture & Pipeline](#2-architecture--pipeline)
3. [Repository Structure](#3-repository-structure)
4. [Ownership Map (P1–P8)](#4-ownership-map-p1p8)
5. [Quick Start](#5-quick-start)
6. [Environment Variables](#6-environment-variables)
7. [Database & Migrations](#7-database--migrations)
8. [Running the Backend](#8-running-the-backend)
9. [Running the Frontend](#9-running-the-frontend)
10. [Running Ingestion](#10-running-ingestion)
11. [Testing Requirements](#11-testing-requirements)
12. [Branching & Git Workflow](#12-branching--git-workflow)
13. [Naming Conventions](#13-naming-conventions)
14. [Coding Conventions](#14-coding-conventions)
15. [API Reference](#15-api-reference)
16. [Definition of Done](#16-definition-of-done)
17. [Hardware Notes](#17-hardware-notes)

---

## 1. Project Overview

The system answers questions over hundreds of institutional PDFs by:

- Finding the right **passage**, not just the right document
- Answering **only** from retrieved content, with inline citations
- **Refusing** when confidence is too low, rather than hallucinating
- **Detecting conflicts** when two "current" versions of a document disagree
- Enforcing strict **tenant isolation** — no data bleeds across organisations

### Why this architecture?

Naive chunk-and-embed RAG underperforms on this corpus because:
1. Policy documents are heavily structured (numbered sections, nested clauses, cross-references) — heading-aware chunking + coarse routing restores that structure.
2. Dense embeddings are structurally bad at matching exact identifiers (GR numbers, form codes) — hybrid retrieval (dense + BM25, fused with Reciprocal Rank Fusion) covers the gap.

### Non-functional requirements (every file must respect these)

| Requirement | Rule |
|---|---|
| **Traceability** | Every answer traces to a specific `(document, section, chunk)`. IDs are carried through unbroken. |
| **Tenant isolation** | Every table query is scoped by `tenant_id`. No exceptions. |
| **Bounded cost** | Expensive ops (LLM routing, cross-encoder reranking) run only on already-narrowed candidate sets. |
| **Graceful degradation** | Every Priority 2 stage has a Priority 1 fallback. A missing module or exception must NOT crash the request. |

---

## 2. Architecture & Pipeline

```
PDF Documents
    │
    ▼
Stage 0 ─ Ingestion (offline)
    ocr.py ─► chunker.py ─► metadata_tagger.py ─► loader.py
    [P2] summarizer.py, section_tree.py, glossary_builder.py
    │
    ├── documents table (with summary, section_tree)
    ├── chunks table (with embedding, text_search tsvector)
    └── glossary table
         │
         ▼
Stage 1 ─ Query Understanding & Rewriting [P4, Priority 2]
    query_rewriter.py  →  RewriteResult
         │
         ▼
Stage 2 ─ Coarse Routing [P2, Priority 2]
    routing.py  →  list[{document_id, section_path}]
         │
         ▼
Stage 3 ─ Fine-Grained Hybrid Retrieval [P2]
    dense_retrieval.py + hybrid_retrieval.py (P2) + RRF
         │
         ▼
Stage 4 ─ Reranking [P3, Priority 2]
    reranker.py (bge-reranker-base)
         │
         ▼
Stage 5 ─ Grounded Generation [P4 + P5]
    generator.py → grounding.py → conflict_detector.py
         │
         ▼
    SSE stream: token / clarify / final events
```

### Priority Definitions

| Priority | Meaning |
|---|---|
| **Priority 1** | Must work end-to-end; the demo spine. Build first, always. |
| **Priority 2** | Differentiators. Built once Priority 1 is solid. Every P2 item has a P1 fallback. |
| **Priority 3** | Out of scope (semantic caching, analytics dashboard, incremental re-indexing automation). Do not build. |

---

## 3. Repository Structure

```
.
├── backend/
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── db/
│   │   └── migrations/                  [P2]
│   └── app/
│       ├── main.py                      [P2] FastAPI app, wires all routers
│       ├── config.py                    [P2] env vars via pydantic-settings
│       ├── database.py                  [P2] async SQLAlchemy engine/session
│       ├── schemas.py                   [P2] Pydantic models for all boundaries
│       ├── deps.py                      [P2] shared FastAPI dependencies
│       ├── ingestion/                   [P1 — whole folder]
│       │   ├── ocr.py
│       │   ├── chunker.py
│       │   ├── metadata_tagger.py
│       │   ├── loader.py
│       │   ├── run_ingestion.py
│       │   ├── summarizer.py            [P2, Priority 2]
│       │   ├── section_tree.py          [P1, Priority 2]
│       │   └── glossary_builder.py      [P1, Priority 2]
│       ├── retrieval/                   
│       │   ├── embeddings.py            [P3]
│       │   ├── indexer.py               [P3]
│       │   ├── dense_retrieval.py       [P2]
│       │   ├── hybrid_retrieval.py      [P2, Priority 2]
│       │   ├── routing.py               [P2, Priority 2]
│       │   ├── reranker.py              [P3, Priority 2]
│       │   └── router.py                [P2] POST /retrieve
│       ├── generation/
│       │   ├── prompts.py               [P4]
│       │   ├── generator.py             [P4] full pipeline orchestration
│       │   ├── query_rewriter.py        [P4, Priority 2]
│       │   ├── router.py                [P4] POST /chat (SSE)
│       │   ├── grounding.py             [P5]
│       │   └── conflict_detector.py     [P5, Priority 2]
│       ├── auth/                        [P6 — whole folder]
│       │   ├── models.py
│       │   ├── security.py
│       │   ├── tenancy.py
│       │   └── router.py
│       └── eval/                        [P8 — whole folder]
│           ├── gold_set.py
│           ├── harness.py
│           ├── report.py
│           └── run_eval.py
├── frontend/
│   └── src/
│       ├── main.tsx                     [P7]
│       ├── App.tsx                      [P7]
│       ├── api/
│       │   └── client.ts                [P7]
│       ├── auth/                        [P6 — whole folder]
│       │   └── Login.tsx
│       └── chat/                        [P7 — whole folder]
│           └── ChatPage.tsx
├── eval/
│   └── gold_qa.json                     [P8]
├── docs/
├── .env.example
├── .gitignore
└── README.md
```

---

## 4. Ownership Map (P1–P8)

| Tag | Files owned | Priority 1 responsibility | Priority 2 responsibility |
|-----|-------------|--------------------------|--------------------------|
| **P1** | `ingestion/*` | OCR-parse PDFs (Marker), heading-aware chunking, metadata tagging, load to DB | Per-doc summary, section-tree extraction, acronym/entity glossary |
| **P2** | `app/main.py`, `config.py`, `database.py`, `schemas.py`, `deps.py`, `db/migrations/`, `retrieval/dense_retrieval.py`, `hybrid_retrieval.py`, `routing.py`, `retrieval/router.py` | Schema + migrations, dense retrieval with metadata filter, `/retrieve` endpoint, integrate whole backend | BM25 + RRF hybrid fusion, coarse routing (doc candidate selection + section-tree reasoning) |
| **P3** | `retrieval/embeddings.py`, `indexer.py`, `reranker.py` | Embedding wrapper, batch indexing job | Cross-encoder reranking (bge-reranker-base) |
| **P4** | `generation/prompts.py`, `generator.py`, `query_rewriter.py`, `generation/router.py` | Grounded cited answer generation; `/chat` SSE endpoint; orchestrates full pipeline (Section 6 call order) | Query rewriting: acronym expansion, metadata predicates, decomposition, clarify-then-fallback |
| **P5** | `generation/grounding.py`, `conflict_detector.py` | Refusal decision (confidence thresholds per Section 9) | Version-conflict detection and dual-surfacing |
| **P6** | `auth/*`, `frontend/src/auth/*` | Login, JWT, tenant scoping, `get_current_user()` | Feedback capture endpoint (`POST /feedback`) |
| **P7** | `frontend/src/*` (excluding `auth/`) | Chat UI: ask → streamed cited answer / clarifying question / refusal / conflict display | Feedback buttons, UI polish |
| **P8** | `eval/*`, `eval/gold_qa.json` | Gold Q&A set (30–50 questions), eval harness: retrieval hit-rate@k, answer faithfulness, hallucination rate | Failure-by-stage attribution report (routing / retrieval / generation) |

> **Rule**: Need something from a file you don't own? Call the function or hit the endpoint using the exact signature in Section 6 of the spec. **Never edit someone else's file.**

---

## 5. Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+ (for frontend)
- PostgreSQL 15+ with `pgvector` extension
- NVIDIA GPU with 4–6 GB VRAM (P1 only, for Marker OCR)

### Backend setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd genai-enterprise-knowledge-assistant

# 2. Create and activate virtual environment
python -m venv env
# Windows:
env\Scripts\activate
# Linux/macOS:
source env/bin/activate

# 3. Install dependencies
# For development (includes linting, type-checking, and test tools):
pip install -r backend/requirements-dev.txt
# requirements-dev.txt starts with "-r requirements.txt", so this installs
# everything in requirements.txt automatically — you do NOT need to run both.
#
# For production / CI (runtime dependencies only):
#   pip install -r backend/requirements.txt

# 4. Copy and populate env file
cp .env.example .env
# Edit .env with your OpenAI key, database URL, JWT secret, etc.

# 5. Apply database migrations
cd backend
alembic upgrade head
cd ..

# 6. Start the development server
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend setup

```bash
cd frontend
npm install
npm run dev
```

---

## 6. Environment Variables

Copy `.env.example` to `.env` and fill in all required values. **Never commit `.env`** — it is in `.gitignore`.

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | OpenAI API key |
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `JWT_SECRET_KEY` | ✅ | Long random string for HMAC JWT signing |
| `JWT_ALGORITHM` | — | Default: `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | — | Default: `60` |
| `APP_ENV` | — | `development` or `production` |
| `LOG_LEVEL` | — | Default: `INFO` |
| `EMBEDDING_MODEL` | — | Default: `text-embedding-3-small` |
| `LLM_MODEL` | — | Default: `gpt-4o-mini` |
| `DENSE_RETRIEVAL_TOP_K` | — | Default: `25` |
| `RERANKER_TOP_N` | — | Default: `5` |
| `REFUSAL_SCORE_THRESHOLD` | — | Default: `0.72` |
| `OCR_DEVICE` | — | `auto` (default) / `cuda` / `cpu` — OCR device for Marker. `auto` detects CUDA at runtime. |
| `VITE_API_BASE_URL` | — | Default: `http://localhost:8000` |

All settings are read through `app.config.Settings`. **Never call `os.environ` directly outside `config.py`.**

---

## 7. Database & Migrations

- **Owner: P2.** Nobody else writes migration files.
- Migrations live in `backend/db/migrations/versions/`.
- Always run `alembic upgrade head` after pulling changes that include new migrations.

```bash
# Create a new migration (P2 only)
cd backend
alembic revision --autogenerate -m "short_description"

# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1
```

---

## 8. Running the Backend

```bash
cd backend

# Development (auto-reload)
uvicorn app.main:app --reload

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

API docs available at `http://localhost:8000/docs` (Swagger UI) and `/redoc`.

---

## 9. Running the Frontend

```bash
cd frontend
npm run dev        # development server at http://localhost:5173
npm run build      # production build (only when explicitly needed)
```

---

## 10. Running Ingestion

Ingestion now has **two paths** — both call the same `ingest_document()` function internally:

### Option A — Upload API (recommended for production)

Admin users can upload PDFs through the frontend (`/upload`) or directly via the API:

```bash
curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@path/to/doc.pdf" \
  -F "department=HR" \
  -F "doc_type=policy"
# Returns immediately: { "document_id": "...", "ingestion_status": "pending" }

# Poll for completion:
curl http://localhost:8000/documents/<document_id>/status \
  -H "Authorization: Bearer <token>"
```

### Option B — CLI batch job (P1 dev / bulk loading)

```bash
cd backend
python -m app.ingestion.run_ingestion <path/to/pdf> <tenant_id> <department> <doc_type>
```

### GPU / CPU support

OCR (Marker) runs on **GPU if available, CPU otherwise** — no manual config needed.
Set `OCR_DEVICE` in your `.env` to override:

| `OCR_DEVICE` | Behaviour |
|---|---|
| `auto` (default) | CUDA if `torch.cuda.is_available()`, else CPU |
| `cuda` | Force GPU (fails if CUDA is not available) |
| `cpu` | Force CPU (slower, works everywhere) |

### After ingestion — embed chunks (P3)

```bash
python -m app.retrieval.indexer
```

---

## 11. Testing Requirements

### Framework

- **Backend**: `pytest` + `pytest-asyncio`
- **Frontend**: Vitest (to be configured by P7)

### Rules

1. One test file per module: `tests/test_<module>.py`
2. All test modules import shared fixtures from `tests/conftest.py` (owned by P2). **Do not invent new fixture setups.**
3. Tests use an **in-memory SQLite** database (configured in `conftest.py`) — do not require a running PostgreSQL for unit tests.
4. Every public function that another module calls must have at least one test covering the happy path and one covering a failure/fallback.
5. Priority 2 code must have a test that verifies it falls back to Priority 1 behaviour when it raises an exception.

### Running tests

```bash
cd backend

# Run all tests
pytest

# Run tests for a specific module
pytest tests/test_retrieval.py -v

# Run with coverage report
pytest --cov=app --cov-report=html

# Run only Priority 1 tests
pytest -m "priority1"
```

### Linting and formatting

```bash
# Format (must pass before PR)
black app/ tests/

# Lint
ruff check app/ tests/

# Type check
mypy app/
```

---

## 12. Branching & Git Workflow

### Branch naming convention

```
<type>/<person-tag>/<short-description>
```

| Type | When to use |
|---|---|
| `feat` | New functionality |
| `fix` | Bug fix |
| `chore` | Tooling, deps, config, refactor |
| `test` | Adding or fixing tests |
| `docs` | Documentation only |

**Examples:**
```
feat/p1/heading-aware-chunker
feat/p2/dense-retrieval-endpoint
feat/p4/grounded-answer-generation
fix/p5/refusal-threshold-off-by-one
test/p3/reranker-fallback
docs/p2/alembic-migration-guide
```

### Workflow

```
main  ←─── protected; requires PR + review
  │
  └── feat/p1/ocr-parser
  └── feat/p2/dense-retrieval-endpoint
  └── feat/p4/chat-sse-endpoint
  ...
```

1. **Branch from `main`** when starting a task.
2. **Never commit directly to `main`**.
3. Keep branches **focused** — one file or one logical change per PR wherever possible. This minimises cross-person merge conflicts.
4. **Rebase, don't merge** when pulling in upstream changes: `git rebase origin/main`.
5. Open a **Pull Request** using the PR template (`.github/PULL_REQUEST_TEMPLATE/`).
6. At least **one other team member reviews** before merge.
7. **Squash and merge** into main to keep history clean.

### Commit message convention

```
<type>(<scope>): <short summary>

[optional body]

[optional footer: Closes #issue]
```

**Examples:**
```
feat(ingestion): add heading-aware chunker with section_path output
fix(retrieval): correct pgvector cosine similarity direction
test(grounding): add fallback test when reranker is unavailable
chore(deps): pin sqlalchemy to 2.0.30
```

---

## 13. Naming Conventions

| Category | Convention | Example |
|---|---|---|
| Python files | `snake_case` | `dense_retrieval.py` |
| Python functions / variables | `snake_case` | `retrieve_chunks()`, `top_k` |
| Python classes / Pydantic models | `PascalCase` | `ChunkResult`, `RewriteResult` |
| Python constants | `UPPER_SNAKE_CASE` | `REFUSAL_SCORE_THRESHOLD` |
| TypeScript files | `PascalCase` (components), `camelCase` (utils) | `ChatPage.tsx`, `client.ts` |
| TypeScript types / interfaces | `PascalCase` | `ChunkResult`, `FinalEvent` |
| Git branches | `<type>/<p-tag>/<kebab-case>` | `feat/p2/hybrid-retrieval` |
| Commit messages | Conventional Commits format | `feat(gen): add conflict detection` |
| DB tables | `snake_case`, plural | `chunks`, `enterprises`, `queries` |
| DB columns | `snake_case` | `tenant_id`, `version_status` |
| API endpoints | `kebab-case`, versioned if needed | `/auth/login`, `/retrieve`, `/chat` |

---

## 14. Coding Conventions

These are **mandatory** — they are what keeps 8 independently-generated codebases mergeable.

### Python

- **Python 3.11+**, FastAPI, `async/await` for **all** I/O (DB, HTTP, LLM calls).
- **Type hints on every function signature.** All structured data crossing a function or API boundary must be a Pydantic model from `schemas.py` — **never a raw `dict`**.
- **Docstrings** on every public function: one-line summary, then `Args:` / `Returns:` in Google style.
- **Config**: read all settings through `config.py`'s `Settings` object. Never call `os.environ` directly outside that file.
- **Errors**: raise typed exceptions defined in your own module. Never let a raw, unhandled exception cross into another module's code. API-facing errors always return `{ error, detail }`.
- **Logging**: use Python's `logging` module. Add `logger = logging.getLogger(__name__)` at the top of each file. **No `print()` in application code.**
- **Imports**: absolute imports rooted at `app.` (e.g., `from app.retrieval.dense_retrieval import retrieve_chunks`). No relative imports, no wildcard imports.
- **Function signatures**: must match Section 6 of the spec exactly — same parameter names, order, and types.
- **Formatting**: `black` (4-space indents, double quotes, trailing commas). **Passes before any PR.**
- **Priority 2 code must fail safe**: wrap in `try/except` so a missing dependency or runtime error falls back to Priority 1 behaviour.

### TypeScript / Frontend

- `prettier` formatting (2-space indents).
- No `any` types at API boundaries — define TypeScript interfaces matching the backend Pydantic models.
- All API calls go through `src/api/client.ts`.

---

## 15. API Reference

Full interactive docs: `http://localhost:8000/docs`

### Authentication

| Method | Endpoint | Owner | Description |
|---|---|---|---|
| `POST` | `/auth/login` | P6 | Login → `{ access_token, tenant_id, user_id, role }` |
| `GET` | `/auth/me` | P6 | Current user identity |
| `POST` | `/feedback` | P6 (P2) | Thumbs up/down feedback |

### Retrieval

| Method | Endpoint | Owner | Description |
|---|---|---|---|
| `POST` | `/retrieve` | P2 | Retrieve top-k chunks for a query |

### Generation

| Method | Endpoint | Owner | Description |
|---|---|---|---|
| `POST` | `/chat` | P4 | Stream grounded answer via SSE |

### Error envelope (all endpoints)

```json
{ "error": "string", "detail": "string" }
```

### SSE event types (`/chat`)

```json
// Token (streaming)
{ "type": "token", "content": "..." }

// Clarify (Priority 2 only)
{ "type": "clarify", "question": "..." }

// Final
{
  "type": "final",
  "answer": "...",
  "citations": [{ "chunk_id": "...", "document_id": "...", "section_path": "...", "source_path": "..." }],
  "confidence": 0.87,
  "refused": false,
  "refusal_reason": null,
  "conflict": false
}
```

---

## 16. Definition of Done

Before raising a PR, verify every item applies:

- [ ] Only files owned by my tag were created or modified (see Section 3 of the spec)
- [ ] Every public function that other modules call matches its Section 6 signature exactly
- [ ] All structured data uses a Pydantic model — no raw `dict` at any boundary
- [ ] Priority 1 work is complete and correct before any Priority 2 work was attempted
- [ ] Priority 2 code fails safe to its Priority 1 fallback if a dependency is missing or it raises
- [ ] `tenant_id` is threaded through every DB query I touched
- [ ] No hardcoded config or secrets — everything goes through `config.py`'s `Settings`
- [ ] A test file exists or was updated for the new logic
- [ ] `black`, `ruff`, and `mypy` all pass (backend)

---

## 17. Hardware Notes

| Owner | Hardware needed | Why |
|---|---|---|
| **P1** (Ingestion) | Any machine; NVIDIA GPU optional (4–6 GB VRAM, e.g. RTX 4050) | Marker OCR runs on CPU or GPU. GPU is faster but not required — `OCR_DEVICE=auto` detects and uses CUDA if present, falls back to CPU silently. |
| **Everyone else** | Any standard machine, no GPU | DB access, embeddings (API), reranking (CPU), LLM calls (API), auth, frontend, eval all run on CPU or go through a network API call. |

---

## Models used

| Component | Model | Notes |
|---|---|---|
| LLM (generation, rewriting, routing, confidence) | `gpt-4o-mini` | One model used consistently everywhere |
| Embeddings | `text-embedding-3-small` | Chunk embeddings, query embeddings, Stage 2a summary-match |
| Reranker (Priority 2) | `bge-reranker-base` via FlagEmbedding | CPU-only, no GPU needed |
| OCR / document parsing | Marker (open-source PDF→structured-markdown) | GPU optional (faster); CPU fully supported. Fallback: GOT-OCR2.0 |

---

*This README is the team's single operational reference.  If something in your implementation diverges from the contracts in this document or in the engineering spec (`docs/spec/engineering_spec_v1.pdf`), open an issue or raise it in the team channel before merging.*
