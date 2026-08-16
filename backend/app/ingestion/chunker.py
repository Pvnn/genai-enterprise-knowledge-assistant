"""Stage 0 – Heading-aware chunking.

Owner: P1  |  Priority: 1
Splits structured markdown (output of ocr.py) into chunks that respect
heading boundaries.  Each chunk carries its section_path so traceability is
preserved all the way through to citations.
"""

import logging

logger = logging.getLogger(__name__)


def chunk_document(markdown: str, document_id: str) -> list[dict]:
    """Split a structured-markdown document into heading-aware chunks.

    Args:
        markdown: Structured markdown string from ocr.parse_document().
        document_id: UUID string of the parent document record.

    Returns:
        list[dict]: List of chunk dicts, each containing:
            - text (str): The chunk text.
            - section_path (str): Heading breadcrumb, e.g. "3 > 3.2 > 3.2.1".
            - document_id (str): Parent document UUID.
    """
    raise NotImplementedError("P1: implement chunk_document() in chunker.py")
