"""Stage 0, Priority 2 – Section-tree (heading hierarchy) extraction.

Owner: P1  |  Priority: 2
Extracts the heading hierarchy from a structured-markdown document and stores
it as JSONB in documents.section_tree.  Used by Stage 2b LLM section routing.
Fallback: if this module is unavailable, scoped_sections is None and retrieval
searches the full tenant corpus.
"""

import logging

logger = logging.getLogger(__name__)


def extract_section_tree(markdown: str) -> dict:
    """Extract a nested heading tree from a structured-markdown document.

    Args:
        markdown: Structured markdown from ocr.parse_document().

    Returns:
        dict: Nested dict representing the heading hierarchy.
              Example: {"1 Introduction": {"1.1 Background": {}, ...}, ...}
    """
    raise NotImplementedError("P1: implement extract_section_tree() in section_tree.py")
