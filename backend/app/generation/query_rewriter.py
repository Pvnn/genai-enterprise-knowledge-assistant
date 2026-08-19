"""Stage 1, Priority 2 – Query rewriting.

Owner: P4  |  Priority: 2
Performs acronym expansion (from the glossary table), metadata predicate
extraction, compound-question decomposition, and produces separate BM25 /
dense phrasings.  Also decides whether a clarifying question is needed.
Depends on P1's glossary table for acronym expansion.
Fallback: if this module is unavailable or raises, generator.py uses the raw
query as-is for both BM25 and dense, with no auto metadata filters and no
sub-query decomposition.

Notes flagged for the team (not silently decided):

1. Glossary lookup queries the `Glossary` ORM model (app/models.py) directly
   with a plain SELECT scoped by tenant_id — there's no existing helper
   function for this, so this is the narrowest reasonable way to read it.

2. This module has its own AsyncOpenAI client (separate from generator.py's)
   to avoid a circular import — generator.py imports from this module, so
   this module must not import from generator.py.

3. On any parse failure or missing field in the LLM's JSON response, this
   falls back to a raw-query passthrough RewriteResult (same shape
   generator.py itself falls back to when this module isn't available at
   all) — so there are two layers of the same safe fallback, not one.

4. QUERY_REWRITER_SYSTEM (prompts.py) asks the model to return a "role"
   field inside metadata_filters, but MetadataFilters (schemas.py, owned by
   P2) only has department/doc_type/version_status — no role field exists.
   Any "role" value the model returns is simply dropped here rather than
   causing an error. Flagging the mismatch between the prompt and the
   schema for the team — either the prompt should stop asking for it, or
   P2 should add it to MetadataFilters.
"""

import json
import logging
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.generation.prompts import QUERY_REWRITER_SYSTEM, query_rewriter_user
from app.models import Glossary
from app.schemas import MetadataFilters, RewriteResult

logger = logging.getLogger(__name__)

settings = get_settings()
_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def rewrite(
    raw_query: str,
    tenant_id: UUID,
    session: AsyncSession,
) -> RewriteResult:
    """Rewrite and expand a raw user query.

    Args:
        raw_query: The original query string from the user.
        tenant_id: Tenant scope (for glossary lookup).
        session: Async database session.

    Returns:
        RewriteResult: Expanded query, metadata filters, BM25/dense variants,
                       sub-queries, and optional clarifying question.
    """
    glossary = await _load_glossary(session, tenant_id)
    messages = [
        {"role": "system", "content": QUERY_REWRITER_SYSTEM},
        {"role": "user", "content": query_rewriter_user(raw_query, glossary)},
    ]

    response = await _client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        response_format={"type": "json_object"},
    )

    try:
        data = json.loads(response.choices[0].message.content)
        filters_data = data.get("metadata_filters") or {}
        return RewriteResult(
            expanded_query=data["expanded_query"],
            metadata_filters=MetadataFilters(
                department=filters_data.get("department"),
                doc_type=filters_data.get("doc_type"),
                version_status=filters_data.get("version_status"),
            ),
            bm25_variant=data["bm25_variant"],
            dense_variant=data["dense_variant"],
            sub_queries=data.get("sub_queries") or [],
            needs_clarification=bool(data.get("needs_clarification", False)),
            clarifying_question=data.get("clarifying_question"),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        logger.warning("query_rewriter: could not parse LLM response, falling back to raw query")
        return _passthrough(raw_query)


async def _load_glossary(session: AsyncSession, tenant_id: UUID) -> dict[str, str]:
    """Loads the tenant's acronym/entity glossary (P1's glossary table).

    Args:
        session: Async database session.
        tenant_id: Tenant to scope the lookup to.

    Returns:
        A dict of term -> expansion. Empty if the tenant has no glossary
        entries yet (e.g. P1's glossary_builder.py hasn't run).
    """
    result = await session.execute(select(Glossary).where(Glossary.tenant_id == tenant_id))
    rows = result.scalars().all()
    return {row.term: row.expansion for row in rows}


def _passthrough(raw_query: str) -> RewriteResult:
    """The same safe fallback shape generator.py uses when this module is unavailable."""
    return RewriteResult(
        expanded_query=raw_query,
        metadata_filters=MetadataFilters(),
        bm25_variant=raw_query,
        dense_variant=raw_query,
        sub_queries=[],
        needs_clarification=False,
        clarifying_question=None,
    )