"""Stage 0 – Metadata extraction.

Owner: P1  |  Priority: 1
Extracts department, doc_type, effective_date, and version_status from the
document text/filename.  These fields are stored on both the documents and
chunks tables and are used as hard-constraint filters in retrieval.
"""

import logging

logger = logging.getLogger(__name__)


def tag_metadata(markdown: str, source_path: str) -> dict:
    """Extract metadata tags from document content and path.

    Args:
        markdown: Structured markdown from ocr.parse_document().
        source_path: Original file path, used for heuristic extraction.

    Returns:
        dict: Containing keys: department, doc_type, effective_date,
              version_status.  Any value may be None if not determinable.
    """
    raise NotImplementedError("P1: implement tag_metadata() in metadata_tagger.py")
