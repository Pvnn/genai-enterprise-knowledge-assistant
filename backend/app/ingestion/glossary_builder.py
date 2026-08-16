"""Stage 0, Priority 2 – Acronym / entity glossary builder.

Owner: P1  |  Priority: 2
Auto-builds a corpus-wide acronym/entity glossary and stores it in the
glossary table.  Used by Stage 1 query rewriting (P4) for acronym expansion.
Fallback: if this module is unavailable, acronym expansion is skipped.
"""

import logging

logger = logging.getLogger(__name__)


async def build_glossary(tenant_id: str, chunks: list[dict]) -> list[dict]:
    """Build or update the acronym/entity glossary from ingested chunks.

    Args:
        tenant_id: The tenant whose corpus is being indexed.
        chunks: List of chunk dicts (must include text field).

    Returns:
        list[dict]: List of glossary entries, each with keys:
            - term (str): The acronym or entity.
            - expansion (str): The expanded form.
    """
    raise NotImplementedError("P1: implement build_glossary() in glossary_builder.py")
