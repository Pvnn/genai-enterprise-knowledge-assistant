# OCR and Layout Parsing

**Owner:** P1
**Stage:** 0
**Priority:** 1
**Files:** `backend/app/ingestion/ocr.py`

## What it does

Parses uploaded PDF documents into structured markdown using Docling and RapidOCR. It preserves the document's structure such as headings and tables, which is necessary to support heading-aware chunking since naive extraction loses structural boundaries.

## Example

**Input:** `firstdegree_regulation.pdf`
**Output:** A structured markdown string retaining `#` for main headings and rendering tables in markdown format.

## Depends on / called by

Called by: `run_ingestion.py`

## Fallback behavior

N/A — no fallback, this is the spine.

## Status

Done

## Known issues / open questions

The script uses Docling with RapidOCR configured for standard CPU or CUDA processing. We suppress the Triton compiler since it's unsupported on Windows (`TORCHDYNAMO_DISABLE=1`).

## Tests

Not yet written (`tests/test_ingestion.py` stub to be written).
