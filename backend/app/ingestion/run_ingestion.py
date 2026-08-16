"""Stage 0 – Full ingestion pipeline runner (CLI entry-point).

Owner: P1
Orchestrates ocr -> chunker -> metadata_tagger -> loader for a given file or
directory.  Invokes Priority 2 stages (summarizer, section_tree,
glossary_builder) when available, silently skipping them on ImportError.
"""

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


async def ingest_file(source_path: str | Path, tenant_id: str) -> None:
    """Run the full ingestion pipeline for a single PDF file.

    Args:
        source_path: Path to the PDF.
        tenant_id: Tenant to which this document belongs.
    """
    raise NotImplementedError("P1: implement ingest_file() in run_ingestion.py")


if __name__ == "__main__":
    import asyncio

    if len(sys.argv) < 3:
        print("Usage: python -m app.ingestion.run_ingestion <path> <tenant_id>")
        sys.exit(1)

    asyncio.run(ingest_file(sys.argv[1], sys.argv[2]))
