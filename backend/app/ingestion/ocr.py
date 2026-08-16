"""Stage 0 – Document parsing via Marker (PDF → structured markdown).

Owner: P1  |  Priority: 1
Uses the Marker library for every PDF (not just scans); plain-text extraction
loses table/heading/layout structure even on born-digital PDFs.
Fallback if VRAM is tight: GOT-OCR2.0.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_document(source_path: str | Path) -> str:
    """Parse a PDF file into structured markdown using Marker.

    Args:
        source_path: Absolute or relative path to the PDF file.

    Returns:
        str: Structured markdown representation of the document, preserving
             headings, tables, and layout information.
    """
    raise NotImplementedError("P1: implement parse_document() in ocr.py")
