"""Prompt templates for all LLM calls.

Owner: P4
Centralises every prompt used in generation, query rewriting, and routing.
All prompts are plain strings or functions returning strings; no logic lives
here beyond template construction.
"""

import logging

logger = logging.getLogger(__name__)

# ── Generation (Stage 5) ──────────────────────────────────────────────────────

GROUNDED_ANSWER_SYSTEM = (
    "You are an enterprise knowledge assistant.  Answer ONLY from the provided "
    "passages.  Cite each claim inline using the format "
    "[<document title>, Section <section_path>].  "
    "If the passages do not contain enough information to answer confidently, "
    "say so and do NOT speculate."
)


def grounded_answer_user(query: str, passages: str) -> str:
    """Build the user turn for the grounded-answer prompt.

    Args:
        query: The user question.
        passages: Newline-delimited retrieved passage texts with metadata.

    Returns:
        str: Formatted user message.
    """
    return f"Question: {query}\n\nRelevant passages:\n{passages}"


# ── Query rewriter (Stage 1) ──────────────────────────────────────────────────

QUERY_REWRITER_SYSTEM = (
    "You are a query-understanding model.  Given a user question, output a "
    "JSON object with the following fields exactly: "
    "expanded_query, metadata_filters (department, doc_type, role, version_status), "
    "bm25_variant, dense_variant, sub_queries (list), "
    "needs_clarification (bool), clarifying_question (str or null)."
)


# ── Section routing (Stage 2b) ────────────────────────────────────────────────

SECTION_ROUTING_SYSTEM = (
    "You are a document-routing model.  Given a question and a document "
    "section tree, identify which section(s) most directly govern the "
    "question.  Return a JSON list of section_path strings."
)


# ── Self-confidence (Stage 5 refusal) ─────────────────────────────────────────

CONFIDENCE_CHECK_SYSTEM = (
    "Rate how well the provided passages support the answer on a scale of "
    "high / medium / low.  Reply with exactly one word."
)


# ── Refusal template (Section 9) ──────────────────────────────────────────────

REFUSAL_TEMPLATE = (
    "I couldn't find a passage in the current policy documents that directly "
    "answers this. You may want to check with {department} or rephrase your question."
)

# ── Conflict template (Section 9) ─────────────────────────────────────────────

CONFLICT_TEMPLATE = (
    "There appear to be two conflicting versions on file:\n"
    "• [{doc_a}] (effective {date_a}) states {value_a}\n"
    "• [{doc_b}] (effective {date_b}) states {value_b}\n"
    "Please confirm which applies to your program, or flag this to the "
    "registrar — both documents are currently marked active."
)

def query_rewriter_user(
    raw_query: str,
    glossary: dict[str, str],
    known_metadata_values: dict[str, list[str]] | None = None,
) -> str:
    """Build the user turn for the query-rewriting prompt.

    Args:
        raw_query: The user's original question.
        glossary: term -> expansion pairs for this tenant (P1's glossary table).
        known_metadata_values: The tenant's REAL, currently-stored values for
            department/doc_type/version_status (queried fresh from the
            documents table). Passed in so the model picks from values that
            actually exist instead of inventing a plausible-sounding one that
            won't match anything in the database. Fixed a real bug: without
            this, the model previously guessed values like doc_type="Leave
            Policy" when the real stored value was "Policy" — an exact-match
            SQL filter on the guessed value silently returned zero chunks.

    Returns:
        str: Formatted user message.
    """
    if glossary:
        glossary_text = "\n".join(f"{term} -> {expansion}" for term, expansion in glossary.items())
    else:
        glossary_text = "(no glossary entries for this tenant yet)"

    known_metadata_values = known_metadata_values or {}
    known_lines = []
    for key in ("department", "doc_type", "version_status"):
        values = known_metadata_values.get(key) or []
        if values:
            known_lines.append(f"{key}: {', '.join(sorted(values))}")
    known_text = (
        "\n".join(known_lines)
        if known_lines
        else "(no documents indexed yet for this tenant — do not guess metadata_filters values)"
    )

    return (
        f"Glossary:\n{glossary_text}\n\n"
        f"Known metadata values for this tenant — ONLY use an exact value from "
        f"this list for metadata_filters, or leave the field null if nothing "
        f"here clearly applies. Never invent a value that isn't listed:\n{known_text}\n\n"
        f"User question: {raw_query}"
    )