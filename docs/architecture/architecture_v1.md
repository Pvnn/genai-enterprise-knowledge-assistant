# Architecture Document

## GenAI Enterprise Knowledge Assistant — Retrieval & Generation Pipeline

This document describes the system architecture only — components, data flow, and design rationale — for team alignment. Priority (**P0 / P1 / P2**) is marked inline within each component's description, not as a separate list, so the "what" and the "how important" stay together.

---

## 1. System Overview

```
                         ┌──────────────┬───────────────┐
                         │   INGESTION (offline, per    │
                         │   document, runs on upload)  │
                         └──────────────┬───────────────┘
                                        │
                    OCR-parse → structured markdown → chunk → embed → store
                                        │
                                        ▼
                         ┌──────────────┬───────────────┐
                         │   Postgres + pgvector (Neon) │
                         │   documents / chunks /       │
                         │   embeddings / metadata      │
                         └──────────────┬───────────────┘
                                        │
   ┌───────────────────────────────────────────────────────────────────┐
   │                         QUERY-TIME PIPELINE                       │
   │                                                                   │
   │   User Query                                                      │
   │       │                                                           │
   │       ▼                                                           │
   │  [1] Query Understanding & Rewriting                              │
   │       │                                                           │
   │       ▼                                                           │
   │  [2] Coarse Routing  ──────► (which document(s), which section)   │
   │       │                                                           │
   │       ▼                                                           │
   │  [3] Fine-Grained Hybrid Retrieval (scoped to routed section)     │
   │       │                                                           │
   │       ▼                                                           │
   │  [4] Reranking                                                    │
   │       │                                                           │
   │       ▼                                                           │
   │  [5] Grounded Generation, Citation, Refusal / Conflict Check      │
   │       │                                                           │
   │       ▼                                                           │
   │   Answer + citations, shown in UI, logged for eval & analytics    │
   └───────────────────────────────────────────────────────────────────┘
```

The core design principle: **narrow the search space progressively, and only spend the expensive operations (LLM reasoning, cross-encoder reranking) on the smallest possible slice of the corpus at each step.** This is what lets the system stay fast and accurate as the number of documents grows, instead of every query scanning the entire corpus.

---

## 2. Stage 0 — Ingestion (offline)

**What it does:** Converts raw PDFs/DOCX into structured, chunked, embedded, metadata-tagged records in the database, before any query ever runs.

```
Raw PDF/DOCX
    │
    ▼
OCR-model parser  ──►  captures tables, headings, layout as structured markdown
    │                   (used even for born-digital PDFs, not just scans —
    │                    layout structure is lost by plain text extraction)
    ▼
Heading-aware chunking
    │   e.g. "Section 4.2: Leave Policy" stays as one intact chunk,
    │   rather than being split mid-clause by a fixed token window
    ▼
Metadata tagging per chunk
    │   department, doc_type, effective_date, version_status,
    │   source_path, section_path
    ▼
Embedding generation (dense vector)
    │
    ▼
Store in Postgres: documents table (doc-level) + chunks table (chunk-level)
```

**Why heading-aware over fixed-window chunking:** policy documents are read and cited by section number in real life ("as per Section 4.2"). If a chunk boundary cuts a clause in half, both retrieval and citation quality degrade — the model may cite a fragment that doesn't contain the actual rule.

**Also produced at ingestion time (feeds Stage 2):** a short LLM-generated **document-level summary** for each document, and a lightweight **section tree** (its table of contents / heading hierarchy) — separate from chunk embeddings, and cheap to produce once per document rather than once per chunk.

- Core OCR → chunk → embed → store flow: **P0**
- Document-level summary generation: **P1** (required input for coarse routing)
- Section-tree extraction: **P1** (required input for coarse routing)

---

## 3. Stage 1 — Query Understanding & Rewriting

**What it does:** Transforms the raw user question into a form the retrieval stages can actually use well, before any search runs.

**Example:**

> Raw query: _"can contract faculty carry their EL forward?"_

The rewriting stage produces:

```json
{
  "expanded_query": "Can contract faculty carry forward unutilized Earned Leave (EL) to the next year?",
  "metadata_filters": {
    "department": null,
    "doc_type": "leave_policy",
    "role": "contract_faculty",
    "version_status": "current"
  },
  "bm25_variant": "carry forward earned leave EL contract faculty",
  "dense_variant": "can contract faculty carry unused leave to next year",
  "sub_queries": [] // empty here; populated for compound questions
}
```

**Four things happen in this one stage:**

1. **Acronym/entity expansion** against a glossary built automatically from the corpus during ingestion (EL → Earned Leave, GR → Government Resolution). **P1**
2. **Metadata predicate extraction** — pulls filter values directly out of natural language. This is the mechanism that actually enforces the metadata-filtering requirement; nothing downstream applies a filter the user didn't imply or the UI didn't set. **P1**
3. **Decomposition** — a compound question like _"what's the leave policy and the travel reimbursement policy?"_ is split into two independent sub-queries, retrieved and answered separately, then merged in generation. **P1**
4. **Multi-form generation** — separate phrasings for BM25 (keyword-dense) and dense retrieval (natural phrasing), since one query string is rarely optimal for both. **P1**

**Clarify-then-fallback behavior:** if metadata extraction finds no usable signal (e.g. the query gives no hint of role or department, and the corpus has role-specific variants of the same policy), the system asks a clarifying question first ("Are you asking as a student, faculty, or staff member?"). If the user doesn't answer or the ambiguity can't be resolved, the system falls back to searching without that filter, i.e. across everything. **P1**

- **P0 fallback if rewriting isn't built yet:** the raw query is used as-is for both BM25 and dense retrieval, with no metadata filter applied automatically (filter can still be set manually via UI, e.g. a department dropdown).

---

## 4. Stage 2 — Coarse Routing (document & section narrowing)

This is the stage most teams skip, and it's the one that makes the rest of the pipeline scale. It answers **"which document, and which section of it"** before any passage-level search happens — the way a human clerk would flip to the right chapter of the right binder, rather than scanning every sentence in every binder.

**Two sub-steps, deliberately separated:**

### 4a. Document-level candidate selection — **P1**

```
Rewritten query + metadata filters
        │
        ▼
Filter documents table by metadata (department, version_status, etc.)
        │
        ▼
Compare query against each candidate document's SHORT SUMMARY
(not its full text, not its chunks — the cheap per-document summary
 generated once at ingestion time)
        │
        ▼
Narrow to a small candidate set, e.g. top 3–5 documents
```

**Why this sub-step exists on its own:** without it, the next step (LLM tree-reasoning) would have to reason over the table of contents of _every document in the corpus_ on every single query. That doesn't scale past a handful of documents. Filtering + a cheap summary-level match keeps the expensive reasoning step bounded, regardless of how large the corpus grows.

### 4b. Section-level tree reasoning — **P1**

```
Within each candidate document:

   Leave Policy 2025.pdf
   ├── 1. Purpose
   ├── 2. Eligibility
   ├── 3. Types of Leave
   │    ├── 3.1 Casual Leave
   │    ├── 3.2 Earned Leave
   │    │    ├── 3.2.1 Accrual
   │    │    └── 3.2.2 Carry-forward     ◄── LLM reasons: "this is it"
   │    └── 3.3 Medical Leave
   └── 4. Procedure for Application

   LLM is given the section tree (like a table of contents) and asked:
   "Which section(s) govern this question?" — the same way a person
   would scan a table of contents rather than read the whole document.
```

**Why this beats pure vector search for this corpus:** a chunk titled _"unutilized EL shall not exceed 15 days"_ may live three sections away from anything using the words "carry forward" — a dense-embedding search compares wording, while tree reasoning compares **meaning of structure** ("which section governs this topic"), so it lands on the right section even when phrasing doesn't overlap.

**Output of Stage 2:** a small, precise set of `(document_id, section_path)` pairs — typically 1–3 — that Stage 3 will search within.

**Cost/latency honesty:** this stage adds one or two LLM calls per query. That is the trade-off for interpretability and precision — and it's exactly what's shown to the user as the "explainability" trail ("the assistant navigated to Section 3.2.2 of the 2025 Leave Policy"). If this stage isn't built in time, retrieval falls back to Stage 3 running directly against the full metadata-filtered corpus (see fallback note below).

- **P0 fallback:** skip Stage 2 entirely. Stage 3 runs directly against the metadata-filtered chunk set for the whole corpus. Slower to scale, but fully functional — this is what "naive but correct" looks like if Stage 2 isn't ready in time.

---

## 5. Stage 3 — Fine-Grained Hybrid Retrieval

**What it does:** Within the narrowed scope from Stage 2 (or the full metadata-filtered corpus, in the P0 fallback), runs two retrieval methods in parallel and fuses their results.

```
                 Rewritten query (dense form)  Rewritten query (BM25 form)
                          │                              │
                          ▼                              ▼
              ┌───────────────────┐          ┌───────────────────┐
              │  Dense retrieval  │          │  BM25 retrieval   │
              │  (pgvector cosine │          │  (Postgres        │
              │   similarity)     │          │   tsvector/rank)  │
              └─────────┬─────────┘          └─────────┬─────────┘
                        │                               │
                        │        rank list A            │  rank list B
                        └───────────────┬────────────────┘
                                        ▼
                         Reciprocal Rank Fusion (RRF)
                                        │
                                        ▼
                          Single fused, ranked chunk list
```

**Why hybrid, concretely:** for the query _"can I carry forward my earned leave"_ —

- Dense retrieval finds chunks that are semantically about leave carry-forward, even with different wording.
- BM25 catches the literal terms **"carry forward"** and **"earned leave"** in a nearby clause that dense search may rank lower because its surrounding sentence structure differs.
- **RRF** combines both rank lists by position rather than raw score, so no manual weight-tuning is needed between the two retrieval methods — useful when there's no time to tune on a validation set.

**Metadata filtering is applied here as a hard constraint, not a re-ranking signal** — e.g. `version_status = 'current'` excludes superseded documents from the candidate set entirely, rather than just ranking them lower.

- Dense-only retrieval with metadata filter: **P0**
- BM25 + RRF hybrid fusion: **P1**

---

## 6. Stage 4 — Reranking

**What it does:** Takes the fused top-k chunks (typically top 20–30) from Stage 3 and re-scores them with a cross-encoder model, which reads the query and each candidate chunk _together_ (rather than comparing separately-computed embeddings), producing a more accurate relevance judgment.

```
Fused top-k chunks (e.g. 25)
        │
        ▼
Cross-encoder reranker scores (query, chunk) pairs jointly
        │
        ▼
Top-n chunks (e.g. 5) passed to generation
```

**Why this is usually the single highest-ROI accuracy step:** initial retrieval (dense or BM25) optimizes for speed across the whole candidate pool and can rank a genuinely relevant chunk 8th or 12th. A cross-encoder, applied only to the already-small candidate set, is far more accurate at judging true relevance and reliably promotes the right chunk to the top before it reaches the LLM.

**Cost stays bounded** because reranking only ever runs on a small candidate set — this is the direct payoff of Stages 2 and 3 having already narrowed the field.

- **P1**

---

## 7. Stage 5 — Grounded Generation, Citation, Refusal & Conflict Detection

**What it does:** Generates the final answer strictly from the top reranked chunks, with three possible outcomes.

### Outcome A — Confident, grounded answer

```
Top reranked chunks (with source_path, section_path, effective_date)
        │
        ▼
LLM generates answer using ONLY this content
        │
        ▼
Answer includes inline citation: [Leave Policy 2025, Section 3.2.2]
```

### Outcome B — Refusal (low-confidence retrieval)

If the top reranked score falls below a threshold, or the retrieved chunks don't actually address the question, the system declines to guess:

> _"I couldn't find a passage in the current policy documents that directly answers this. You may want to check with [department] or rephrase your question."_

### Outcome C — Conflict detected (two "current" documents disagree) — **P1**

```
Retrieved chunks include TWO documents both tagged version_status = "current"
that state different values for the same rule
        │
        ▼
System does NOT pick one silently
        │
        ▼
Answer surfaces both, with dates:

"There appear to be two conflicting versions on file:
 • Fee Structure (effective Jan 2024) states ₹45,000/semester
 • Fee Structure (effective Aug 2025) states ₹52,000/semester
 Please confirm which applies to your program, or flag this
 to the registrar — both documents are currently marked active."
```

This is deliberately conservative: a confidently wrong answer on a policy question is worse than a visible admission that the source corpus itself is inconsistent.

- Grounded generation with citation + basic confidence-threshold refusal: **P0**
- Version-conflict detection and dual-surfacing: **P1**

---

## 8. End-to-End Example Trace

**Query:** _"Can I carry forward my earned leave to next year?"_ (asked by a logged-in contract faculty user)

| Stage               | What happens                                                                                                                                                                                                                                       |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Rewriting        | Expands to full form, extracts `role: contract_faculty`, `doc_type: leave_policy`, `version_status: current`; generates BM25 + dense variants                                                                                                      |
| 2a. Doc candidates  | Metadata filter + summary match narrows corpus to `["Leave Policy 2025.pdf", "Contract Faculty Service Rules.pdf"]`                                                                                                                                |
| 2b. Section routing | Tree reasoning selects `Leave Policy 2025.pdf → Section 3.2.2 (Carry-forward)` and `Contract Faculty Service Rules.pdf → Section 5 (Leave Entitlements)`                                                                                           |
| 3. Hybrid retrieval | Runs dense + BM25 within just those two sections; RRF fuses results                                                                                                                                                                                |
| 4. Reranking        | Cross-encoder promotes the chunk stating the actual carry-forward cap to top rank                                                                                                                                                                  |
| 5. Generation       | Answer: _"Yes — up to 15 days of unutilized Earned Leave may be carried forward to the next calendar year. [Leave Policy 2025, Section 3.2.2]. Note: contract faculty are subject to the same cap per Contract Faculty Service Rules, Section 5."_ |
| Logged              | Raw query, rewritten query, routed sections, retrieved chunks, confidence score, and the final answer are all logged for eval and analytics                                                                                                        |

---

## 9. Non-Functional Requirements

- **Traceability:** every answer must be traceable back to a specific `(document, section, chunk)` — this is what Stage 2's routing output and Stage 5's citations both feed.
- **Tenant isolation:** every table and every query is scoped by `tenant_id`; no retrieval or generation step should ever see across-tenant data.
- **Bounded cost under corpus growth:** the expensive operations (LLM tree reasoning in Stage 2, cross-encoder reranking in Stage 4) must only ever operate on a narrowed candidate set, not the full corpus — this is the core scalability property of the whole cascade, not an afterthought bolted onto one stage.
- **Graceful degradation:** each P1 stage has a defined P0 fallback (noted inline above) so the system remains fully functional, just less precise, if a given stage isn't ready.

---

## 10. Priority Recap

- **P0 (must work, end-to-end):** ingestion → metadata-tagged storage → dense retrieval with metadata filter → grounded generation with citation and basic refusal → visible in UI.
- **P1 (the differentiators):** query rewriting with clarify-then-fallback, hybrid BM25+RRF, reranking, coarse document/section routing, version-conflict detection.
- **P2 (mentioned above only where directly relevant, otherwise out of scope for this document):** semantic caching, analytics depth, incremental re-indexing automation.
