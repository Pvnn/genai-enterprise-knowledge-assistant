"""Stage 2, Priority 2 – Coarse document and section routing.

Owner: P2  |  Priority: 2
Stage 2a: metadata filter + summary-embedding match -> top 3-5 candidate docs.
Stage 2b: LLM reads each candidate document's section_tree to pick the
governing section(s).
Returns a list of (document_id, section_path) pairs used to scope Stage 3.
Fallback: if this module is unavailable or raises, return [] (scoped_sections = None)
and dense_retrieval searches the full metadata-filtered corpus.
"""

from __future__ import annotations

import json
import logging
import re
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.schemas import ScopedSection

logger = logging.getLogger(__name__)


def _flatten_section_tree(tree: dict | list | None, prefix: str = "") -> list[str]:
    """Flatten a nested section tree dictionary into a list of section paths."""
    if not tree:
        return []

    paths: list[str] = []
    if isinstance(tree, dict):
        for key, value in tree.items():
            current_path = f"{prefix} > {key}".strip(" >") if prefix else str(key)
            paths.append(current_path)
            if isinstance(value, (dict, list)):
                paths.extend(_flatten_section_tree(value, current_path))
    elif isinstance(tree, list):
        for item in tree:
            if isinstance(item, str):
                current_path = f"{prefix} > {item}".strip(" >") if prefix else item
                paths.append(current_path)
            elif isinstance(item, dict):
                paths.extend(_flatten_section_tree(item, prefix))
    return paths


def _heuristic_match_sections(
    query: str,
    candidate_docs: list[dict],
) -> list[dict]:
    """Fallback keyword matching over section paths when LLM is unavailable."""
    keywords = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2]
    if not keywords:
        return []

    scored_sections: list[tuple[float, dict]] = []

    for doc in candidate_docs:
        doc_id = doc["id"]
        sections = doc["section_paths"]
        for section in sections:
            sec_lower = section.lower()
            match_score = sum(1 for kw in keywords if kw in sec_lower)
            if match_score > 0:
                scored_sections.append(
                    (
                        float(match_score),
                        {"document_id": doc_id, "section_path": section},
                    )
                )

    scored_sections.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored_sections[:3]]


async def _llm_reason_sections(
    query: str,
    candidate_docs: list[dict],
) -> list[dict]:
    """Use configured LLM to reason over candidate documents' section trees."""
    settings = get_settings()

    doc_context_blocks = []
    for doc in candidate_docs:
        tree_repr = json.dumps(doc["raw_tree"], indent=2) if doc["raw_tree"] else str(doc["section_paths"])
        doc_context_blocks.append(
            f"Document ID: {doc['id']}\nTitle: {doc['title']}\nSection Tree:\n{tree_repr}"
        )

    prompt = (
        "You are an enterprise document router.\n"
        "Given a user query and candidate document structures, identify 1 to 3 exact section paths "
        "that most likely contain the answer to the query.\n\n"
        f"Candidate Documents:\n{'---'.join(doc_context_blocks)}\n\n"
        f"User Query: {query}\n\n"
        "Return ONLY a JSON list of objects in the following format:\n"
        '[{"document_id": "<UUID>", "section_path": "<exact section path from tree>"}]\n'
        "If no sections match, return []."
    )

    try:
        # Try OpenAI if configured with a real key
        if settings.openai_api_key and not settings.openai_api_key.startswith("sk-...") and not settings.openai_api_key.endswith("..."):
            from openai import AsyncOpenAI

            client_kwargs: dict = {"api_key": settings.openai_api_key, "timeout": 5.0}
            if settings.openai_api_key and settings.openai_api_key.startswith("gsk_"):
                client_kwargs["base_url"] = "https://api.groq.com/openai/v1"
            client = AsyncOpenAI(**client_kwargs)
            response = await client.chat.completions.create(
                model=settings.llm_model or "gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            content = response.choices[0].message.content or "[]"
            # Extract JSON from output
            match = re.search(r"\[.*\]", content, re.DOTALL)
            if match:
                raw_json = json.loads(match.group(0))
                return [
                    {
                        "document_id": UUID(str(item["document_id"])),
                        "section_path": str(item["section_path"]),
                    }
                    for item in raw_json
                    if "document_id" in item and "section_path" in item
                ]
    except Exception as exc:
        logger.warning("LLM section reasoning failed: %s; falling back to heuristic", exc)

    return _heuristic_match_sections(query, candidate_docs)


async def route_query(
    rewritten_query: str,
    tenant_id: UUID,
    session: AsyncSession,
) -> list[ScopedSection]:
    """Select the governing document(s) and section(s) for a query.

    Args:
        rewritten_query: Expanded/rewritten query from Stage 1 (or raw query).
        tenant_id: Tenant scope (hard constraint).
        session: Async database session.

    Returns:
        list[ScopedSection]: 1-3 ScopedSection objects (document_id, section_path).

        Bug fixed here: this function used to return plain dicts with the same
        keys, but dense_retrieval.py's retrieve_chunks()/_retrieve_pgvector()/
        _retrieve_fallback() all type-hint scoped_sections as
        list[ScopedSection] and access fields via dot notation
        (s.document_id, not s["document_id"]). That mismatch only ever
        surfaced once this function's LLM call actually succeeded and
        returned a non-empty list — every earlier test hit an auth error
        here and fell through to scoped_sections=[]/None, which never
        exercised the mismatched attribute access. Converting to real
        ScopedSection objects here, at the boundary, matches the contract
        every caller already expects.
    """
    if not rewritten_query.strip():
        return []

    try:
        # Stage 2a: Query candidate documents having summary or section_tree
        query_sql = """
            SELECT 
                id, 
                title, 
                summary, 
                section_tree
            FROM documents
            WHERE tenant_id = :tenant_id
        """
        result = await session.execute(text(query_sql), {"tenant_id": str(tenant_id)})
        rows = result.fetchall()

        if not rows:
            return []

        # Stage 2a: Score candidate documents against the query
        keywords = [w.lower() for w in re.findall(r"\w+", rewritten_query) if len(w) > 2]
        scored_candidates: list[tuple[float, dict]] = []

        for row in rows:
            doc_id = UUID(str(row.id))
            raw_tree = row.section_tree
            if isinstance(raw_tree, str):
                try:
                    raw_tree = json.loads(raw_tree)
                except Exception:
                    raw_tree = None

            section_paths = _flatten_section_tree(raw_tree)
            summary_text = (row.summary or "") + " " + (row.title or "")

            # Relevance score from keyword overlap in summary + title + sections
            score = 0.0
            if keywords:
                summary_lower = summary_text.lower()
                score += sum(summary_lower.count(kw) for kw in keywords) * 2.0
                sections_lower = " ".join(section_paths).lower()
                score += sum(sections_lower.count(kw) for kw in keywords)

            candidate_info = {
                "id": doc_id,
                "title": row.title,
                "summary": row.summary,
                "raw_tree": raw_tree,
                "section_paths": section_paths,
            }
            scored_candidates.append((score, candidate_info))

        # Sort candidate documents and keep top 3-5
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        top_candidates = [doc for _, doc in scored_candidates[:5] if doc["section_paths"]]

        if not top_candidates:
            return []

        # Stage 2b: Reason over candidate section trees
        selected_sections = await _llm_reason_sections(rewritten_query, top_candidates)
        return [
            ScopedSection(document_id=s["document_id"], section_path=s["section_path"])
            for s in selected_sections[:3]
        ]

    except Exception as exc:
        logger.exception("Error occurred during Stage 2 coarse routing: %s", exc)
        return []
