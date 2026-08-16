"""Stage 0 – Document parsing via Marker (PDF → structured markdown).

Owner: P1  |  Priority: 1
Uses the Marker library for every PDF (not just scans); plain-text extraction
loses table/heading/layout structure even on born-digital PDFs.
GPU (CUDA) is optional and faster if present; CPU is fully supported.
Fallback OCR model if Marker is unavailable: GOT-OCR2.0.
"""

import logging
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


def _resolve_device(device: str) -> str:
    """Resolve 'auto' to 'cuda' or 'cpu' based on runtime availability.

    Args:
        device: 'auto', 'cuda', or 'cpu'.

    Returns:
        str: 'cuda' if CUDA is available and device is 'auto' or 'cuda',
             otherwise 'cpu'.
    """
    if device == "auto":
        try:
            import torch  # type: ignore[import]
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            logger.warning("torch not installed; defaulting OCR device to cpu")
            return "cpu"
    return device


def parse_document(source_path: str | Path, device: str | None = None) -> str:
    """Parse a PDF file into structured markdown using Marker.

    The device used for the OCR model is resolved in priority order:
      1. The explicit ``device`` argument (if not None).
      2. The ``OCR_DEVICE`` env-var / Settings value (default ``"auto"``).
      3. Auto-detection: CUDA if available, CPU otherwise.

    Args:
        source_path: Absolute or relative path to the PDF file.
        device: Override the OCR device ('auto', 'cuda', or 'cpu').
                If None, reads from Settings.ocr_device.

    Returns:
        str: Structured markdown representation of the document, preserving
             headings, tables, and layout information.
    """
    settings = get_settings()
    resolved_device = _resolve_device(device if device is not None else settings.ocr_device)
    logger.info("parse_document: source=%s device=%s", source_path, resolved_device)
    raise NotImplementedError("P1: implement parse_document() in ocr.py")
