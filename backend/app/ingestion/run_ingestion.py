"""Stage 0 – Full ingestion pipeline runner.

Owner: P1
Provides:
  - ingest_document()  — importable callable used by ingestion/router.py
                         (BackgroundTasks) and any programmatic caller.
  - ingest_file()      — thin wrapper kept for backward-compat.
  - CLI entry-point    — python -m app.ingestion.run_ingestion <path> <tenant_id>
                         <department> <doc_type>

Orchestrates ocr -> chunker -> metadata_tagger -> loader.
Invokes Priority 2 stages (summarizer, section_tree, glossary_builder)
when available, silently skipping them on ImportError or exception.
GPU is optional; device selection is delegated to ocr.parse_document().
"""

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


async def ingest_document(
    file_path: str,
    tenant_id: str,
    department: str,
    doc_type: str,
) -> str:
    """Run the full ingestion pipeline for a single PDF file.

    This is the canonical importable entry-point.  Called by
    ingestion/router.py inside a FastAPI BackgroundTasks job.

    Args:
        file_path: Absolute path to the PDF file on disk.
        tenant_id: Tenant to which this document belongs.
        department: Department metadata tag (e.g. "HR", "Finance").
        doc_type: Document type tag (e.g. "policy", "circular").

    Returns:
        str: UUID of the newly created document record.
    """
    raise NotImplementedError("P1: implement ingest_document() in run_ingestion.py")


async def ingest_file(source_path: str | Path, tenant_id: str) -> None:
    """Backward-compatible wrapper around ingest_document().

    Kept so existing batch callers that only pass (path, tenant_id) continue
    to work.  department and doc_type default to empty strings; P1 should
    extract them from the document itself inside ingest_document().

    Args:
        source_path: Path to the PDF.
        tenant_id: Tenant to which this document belongs.
    """
    await ingest_document(
        file_path=str(source_path),
        tenant_id=tenant_id,
        department="",
        doc_type="",
    )


if __name__ == "__main__":
    import asyncio

    if len(sys.argv) < 5:
        print(
            "Usage: python -m app.ingestion.run_ingestion "
            "<path> <tenant_id> <department> <doc_type>"
        )
        sys.exit(1)

    asyncio.run(
        ingest_document(
            file_path=sys.argv[1],
            tenant_id=sys.argv[2],
            department=sys.argv[3],
            doc_type=sys.argv[4],
        )
    )
