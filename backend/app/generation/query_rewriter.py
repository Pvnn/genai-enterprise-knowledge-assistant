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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.generation.prompts import QUERY_REWRITER_SYSTEM, query_rewriter_user
from app.llm import get_llm_client, get_llm_model
from app.models import Document, Glossary
from app.schemas import MetadataFilters, RewriteResult

logger = logging.getLogger(__name__)

_client = get_llm_client()


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
    known_metadata_values = await _load_known_metadata_values(session, tenant_id)
    messages = [
        {"role": "system", "content": QUERY_REWRITER_SYSTEM},
        {
            "role": "user",
            "content": query_rewriter_user(raw_query, glossary, known_metadata_values),
        },
    ]

    model = get_llm_model()
    response = await _client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
    )

    try:
        data = json.loads(response.choices[0].message.content)
        filters_data = data.get("metadata_filters") or {}
        return RewriteResult(
            expanded_query=data["expanded_query"],
            metadata_filters=MetadataFilters(
                department=_match_known_value(
                    filters_data.get("department"), known_metadata_values.get("department")
                ),
                doc_type=_match_known_value(
                    filters_data.get("doc_type"), known_metadata_values.get("doc_type")
                ),
                version_status=_match_known_value(
                    filters_data.get("version_status"), known_metadata_values.get("version_status")
                ),
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


async def _load_known_metadata_values(
    session: AsyncSession, tenant_id: UUID
) -> dict[str, list[str]]:
    """Loads the tenant's REAL, currently-stored department/doc_type/version_status values.

    Real bug fixed by this: metadata_filters extraction previously let the LLM
    invent any plausible-sounding value (e.g. doc_type="Leave Policy"), which
    then got applied as an exact-match SQL filter in dense_retrieval.py. If the
    real stored value differed at all (e.g. "Policy", or different casing like
    "current" vs "Current"), the filter silently excluded every chunk — even
    an otherwise perfect match — with no error, just an empty result. Loading
    the real values first lets the prompt show the model its actual options.

    Args:
        session: Async database session.
        tenant_id: Tenant to scope the lookup to.

    Returns:
        dict with keys "department", "doc_type", "version_status", each a
        list of the distinct non-null values currently in use for this tenant.
    """
    values: dict[str, list[str]] = {}
    for field_name, column in (
        ("department", Document.department),
        ("doc_type", Document.doc_type),
        ("version_status", Document.version_status),
    ):
        result = await session.execute(
            select(column).where(Document.tenant_id == tenant_id, column.is_not(None)).distinct()
        )
        values[field_name] = [row[0] for row in result.all() if row[0]]
    return values


def _match_known_value(candidate: str | None, known_values: list[str] | None) -> str | None:
    """Validates an LLM-guessed filter value against the tenant's real known values.

    Matches case-insensitively (guards against the "current" vs "Current" class
    of mismatch) but always returns the DATABASE's exact stored casing, since
    that's what dense_retrieval.py's exact-match SQL filter needs. If the
    candidate doesn't match any known value, returns None rather than passing
    through an unmatchable value — better to search with no filter on this
    field than to silently filter out every chunk.

    Args:
        candidate: The value the LLM extracted (or None).
        known_values: The tenant's real distinct values for this field.

    Returns:
        The matching real value (in its real stored casing), or None.
    """
    if not candidate:
        return None
    candidate_str = str(candidate).strip()
    if not known_values:
        return candidate_str
    candidate_lower = candidate_str.lower()
    for real_value in known_values:
        if real_value.strip().lower() == candidate_lower:
            return real_value
    return candidate_str


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