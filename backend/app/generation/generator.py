"""Stage 5 – Grounded answer generation and full pipeline orchestration.

Owner: P4  |  Priority: 1
This file is the single orchestration point for the entire query pipeline.
The call order is specified in Section 6 of the engineering spec:

  1. query_rewriter.rewrite()       [P2 fallback: raw query]
  2. routing.route_query()          [Priority 2; fallback: scoped_sections=None]
  3. dense_retrieval.retrieve_chunks() + hybrid_retrieval (Priority 2)
  4. reranker.rerank()              [Priority 2; fallback: first top_n]
  5. Merge sub-query results
  6. Draft answer via LLM with inline citations
  7. grounding.decide_refusal()     [which calls conflict_detector internally]
  8. Stream the final SSE response

Every Priority 2 step is wrapped in a try/except that falls back to the
Priority 1 behavior rather than crashing the request.

--- Notes flagged for the team (not silently decided — confirm these) ---

1. Ordering of "rerank" vs "merge sub-query results": the module docstring
   above lists rerank (step 4) before merging sub-query results (step 5).
   This implementation instead retrieves per sub-query, MERGES all of those
   chunks into one pool first, then reranks (or trims) that single merged
   pool once. Reranking each sub-query separately would produce scores that
   aren't comparable across sub-queries, so there'd be no correct way to
   merge already-reranked lists. Flagging this reordering explicitly.

2. Citation format gap: GROUNDED_ANSWER_SYSTEM (prompts.py) asks the model
   to cite as "[<document title>, Section ...]", but ChunkResult has no
   title field — only document_id, section_path, and source_path. Passages
   are built using document_id + section_path (see prompts.py's own
   build, which already does this), so citations will show a raw
   document_id rather than a human title until ChunkResult gains a title
   field. Not something P4 can add — ChunkResult is owned by P2.

3. config.py's openai_api_key is Optional (defaults to None), but this
   file's answer-drafting step requires a working OpenAI key with no
   fallback — there is no Priority 1 substitute for "write the answer".
   If the .env doesn't have a real key, this will fail at the OpenAI call,
   not gracefully. Worth confirming with the team the key is actually set.

4. ChatRequest (schemas.py) has no `filters` field, so there is currently
   no way for the UI to pass a manual metadata filter through to Stage 3.
   metadata_filters defaults to empty for the raw-query fallback path.
"""

import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.generation.grounding import decide_refusal  # P5 — required Priority 1 dependency
from app.generation.prompts import GROUNDED_ANSWER_SYSTEM, grounded_answer_user
from app.llm import get_llm_client, get_llm_model
from app.retrieval.dense_retrieval import retrieve_chunks  # P2 — required Priority 1 dependency
from app.retrieval.embeddings import embed_text  # P3 — required Priority 1 dependency
from app.schemas import (
    ChatRequest,
    ChunkResult,
    Citation,
    ClarifyEvent,
    FinalEvent,
    MetadataFilters,
    TokenEvent,
)

logger = logging.getLogger(__name__)
settings = get_settings()
_client = get_llm_client()

# --- Optional Priority 2 dependencies -- each falls back to the Priority 1
# behavior described in the module docstring if missing or if it raises.

try:
    from app.generation.query_rewriter import rewrite as _rewrite_query
except ImportError:
    _rewrite_query = None
    logger.info("query_rewriter.rewrite not available — Stage 1 falls back to raw-query passthrough")

try:
    from app.retrieval.routing import route_query as _route_query
except ImportError:
    _route_query = None
    logger.info("routing.route_query not available — Stage 2 falls back to scoped_sections=None")

try:
    from app.retrieval.hybrid_retrieval import hybrid_retrieve_chunks as _hybrid_retrieve_chunks
except ImportError:
    _hybrid_retrieve_chunks = None
    logger.info("hybrid_retrieve_chunks not available — Stage 3 falls back to dense-only retrieval")

try:
    from app.retrieval.reranker import rerank as _rerank
except ImportError:
    _rerank = None
    logger.info("reranker.rerank not available — Stage 4 falls back to taking the top N as-is")


async def generate_answer(
    request: ChatRequest,
    session: AsyncSession,
) -> AsyncGenerator[dict, None]:
    """Orchestrate the full RAG pipeline and stream SSE events.

    Args:
        request: The validated chat request (query, tenant_id, conversation_id).
        session: Async database session.

    Yields:
        dict: SSE event dicts, produced via `.model_dump(mode="json")` so
        every field (including UUIDs) is already JSON-safe for router.py's
        `json.dumps(event)` call — one of TokenEvent, ClarifyEvent, or
        FinalEvent shapes as defined in app.schemas.
    """
    try:
        # --- Step 1: query rewriting (Priority 2, falls back to raw query) ---
        expanded_query, metadata_filters, sub_queries, clarify = await _get_rewrite(
            session, request.query, request.tenant_id
        )
        if clarify is not None:
            yield ClarifyEvent(question=clarify).model_dump(mode="json")
            return

        # --- Steps 2-3: routing + retrieval, per sub-query ---
        queries_to_run = sub_queries or [expanded_query]
        all_chunks: list[ChunkResult] = []
        for sub_query in queries_to_run:
            all_chunks.extend(
                await _retrieve_for_subquery(session, sub_query, metadata_filters, request.tenant_id)
            )

        # --- Step 5 (done here, before rerank — see docstring note 1): merge ---
        merged = _dedupe_chunks(all_chunks)

        # --- Step 4: rerank the merged pool (or trim to top N if unavailable) ---
        top_chunks = await _rerank_or_take_top_n(expanded_query, merged)

        # --- Step 6: draft the answer ---
        # Skip the LLM call entirely when there are zero chunks — decide_refusal's
        # zero-chunk rule refuses regardless of draft content, so drafting from
        # nothing would just be a wasted API call.
        draft_answer = await _draft_answer(expanded_query, top_chunks) if top_chunks else ""

        # --- Step 7: refusal / conflict decision ---
        decision = await decide_refusal(query=request.query, top_chunks=top_chunks, draft_answer=draft_answer)

        if decision.refused:
            yield FinalEvent(
                answer="",  # FinalEvent.answer is a required str, not Optional — must not be None
                citations=[],
                confidence=decision.confidence,
                refused=True,
                refusal_reason=decision.reason,
                conflict=decision.conflict,
            ).model_dump(mode="json")
            return

        # --- Step 8: stream the answer, then the final event ---
        async for piece in _chunk_for_streaming(draft_answer):
            yield TokenEvent(content=piece).model_dump(mode="json")

        yield FinalEvent(
            answer=draft_answer,
            citations=_build_citations(top_chunks),
            confidence=decision.confidence,
            refused=False,
            refusal_reason=None,
            conflict=decision.conflict,
        ).model_dump(mode="json")

    except Exception:
        # Not explicitly specified in the doc, but without this, an unexpected
        # error anywhere above breaks the SSE stream with no event at all —
        # the frontend would just see a dead connection. Flagging this as an
        # addition: surface a safe refusal event instead of a silent crash.
        logger.exception("generate_answer: unhandled error, surfacing as a refusal event")
        yield FinalEvent(
            answer="",
            citations=[],
            confidence=0.0,
            refused=True,
            refusal_reason="internal_error",
            conflict=False,
        ).model_dump(mode="json")


async def _get_rewrite(
    session: AsyncSession, query: str, tenant_id: UUID
) -> tuple[str, MetadataFilters, list[str], str | None]:
    """Step 1. Returns (expanded_query, metadata_filters, sub_queries, clarifying_question_or_None)."""
    if _rewrite_query is not None:
        try:
            result = await _rewrite_query(raw_query=query, tenant_id=tenant_id, session=session)
            if result.needs_clarification:
                return result.expanded_query, result.metadata_filters, [], result.clarifying_question
            return result.expanded_query, result.metadata_filters, result.sub_queries, None
        except Exception:
            logger.exception("query_rewriter.rewrite raised — falling back to raw-query passthrough")
    return query, MetadataFilters(), [], None


async def _retrieve_for_subquery(
    session: AsyncSession, sub_query: str, filters: MetadataFilters, tenant_id: UUID
) -> list[ChunkResult]:
    """Steps 2-3 for one sub-query: route (if available), then retrieve (dense or hybrid)."""
    scoped_sections = None
    if _route_query is not None:
        try:
            scoped_sections = await _route_query(sub_query, tenant_id, session) or None
        except Exception:
            logger.exception("routing.route_query raised — falling back to scoped_sections=None")

    query_embedding = await embed_text(sub_query)

    if _hybrid_retrieve_chunks is not None:
        try:
            return await _hybrid_retrieve_chunks(
                query_embedding=query_embedding,
                bm25_query=sub_query,
                tenant_id=tenant_id,
                filters=filters,
                top_k=settings.dense_retrieval_top_k,
                session=session,
                scoped_sections=scoped_sections,
            )
        except Exception:
            logger.exception("hybrid_retrieve_chunks raised — falling back to dense-only retrieval")

    return await retrieve_chunks(
        query_embedding=query_embedding,
        tenant_id=tenant_id,
        filters=filters,
        top_k=settings.dense_retrieval_top_k,
        session=session,
        scoped_sections=scoped_sections,
    )


def _dedupe_by_chunk_id(chunks: list[ChunkResult]) -> list[ChunkResult]:
    """Merges chunks pulled from multiple sub-queries, keeping the highest score per unique chunk_id."""
    best: dict[UUID | str, ChunkResult] = {}
    for c in chunks:
        key = c.chunk_id if c.chunk_id else c.text.strip()
        existing = best.get(key)
        if existing is None or c.score > existing.score:
            best[key] = c
    return sorted(best.values(), key=lambda c: c.score, reverse=True)


_dedupe_chunks = _dedupe_by_chunk_id


async def _rerank_or_take_top_n(query: str, chunks: list[ChunkResult]) -> list[ChunkResult]:
    """Step 4: reranks if reranker.py is available, else takes the first top_n as-is."""
    if _rerank is not None and chunks:
        try:
            import asyncio
            return await asyncio.to_thread(_rerank, query, chunks, settings.reranker_top_n)
        except Exception:
            logger.exception("reranker.rerank raised — falling back to retrieval order")
    return chunks[: settings.reranker_top_n]


async def _draft_answer(query: str, chunks: list[ChunkResult]) -> str:
    """Step 6: drafts the grounded answer from the top chunks, using P4's own prompts.py."""
    model = get_llm_model()
    messages = [
        {"role": "system", "content": GROUNDED_ANSWER_SYSTEM},
        {"role": "user", "content": grounded_answer_user(query, _format_passages(chunks))},
    ]
    response = await _client.chat.completions.create(
        model=model,
        messages=messages,
    )
    return response.choices[0].message.content or ""


def _format_passages(chunks: list[ChunkResult]) -> str:
    """Builds the passages block grounded_answer_user() expects."""
    if not chunks:
        return "(no passages retrieved)"
    return "\n\n".join(
        f"[Section: {c.section_path or 'General'}]\n{c.text}" for c in chunks
    )


async def _chunk_for_streaming(text: str, chunk_size: int = 40) -> AsyncGenerator[str, None]:
    """Splits a completed answer into pieces for a live-typing SSE effect."""
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]


def _build_citations(chunks: list[ChunkResult]) -> list[Citation]:
    """Builds the Citation list for the final response (Section 5)."""
    return [
        Citation(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            section_path=c.section_path,
            source_path=c.source_path,
            text=c.text,
        )
        for c in chunks
    ]