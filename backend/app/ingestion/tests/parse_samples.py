"""Docling sanity check script.

Runs Docling against every PDF in fixtures/sample_pdfs/ using native
PyTorch inference on GPU (RTX 4050) or CPU, no vLLM/server required.

Key env var:
    TORCHDYNAMO_DISABLE=1  — MUST be set before any torch/docling import.
    Disables torch.compile's graph capture, which otherwise requires
    Triton (no reliable Windows support). Layout detection then runs
    eager on GPU instead, same as RapidOCR already does.

Usage:
    python backend/app/ingestion/tests/parse_samples.py          # GPU auto
    python backend/app/ingestion/tests/parse_samples.py --cpu    # force CPU
"""

import os

os.environ["TORCHDYNAMO_DISABLE"] = "1"

import argparse
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FIXTURES   = Path(__file__).parent / "fixtures" / "sample_pdfs"
OUTPUT_DIR = Path(__file__).parent / "fixtures" / "docling_output"


def resolve_device(force_cpu: bool):
    """Pick the accelerator device. Returns an AcceleratorDevice enum value."""
    from docling.datamodel.accelerator_options import AcceleratorDevice
    try:
        import torch
        if force_cpu:
            logger.info("Device forced to CPU via --cpu flag.")
            return AcceleratorDevice.CPU
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            logger.info("CUDA available - using GPU: %s", name)
            return AcceleratorDevice.CUDA
        logger.info("CUDA not available - falling back to CPU.")
        return AcceleratorDevice.CPU
    except ImportError:
        logger.warning("torch not installed - defaulting to CPU.")
        return AcceleratorDevice.CPU


def main() -> None:
    ap = argparse.ArgumentParser(description="Task 1 - Docling sanity check on sample PDFs")
    ap.add_argument("--cpu", action="store_true", help="Force CPU even if GPU is available")
    args = ap.parse_args()

    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
    from docling.datamodel.accelerator_options import AcceleratorOptions

    device = resolve_device(args.cpu)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(FIXTURES.glob("*.pdf"))
    if not pdfs:
        logger.error("No PDFs found in %s", FIXTURES)
        sys.exit(1)

    logger.info("Device: %s", device)
    logger.info("Building Docling converter (RapidOCR torch backend) ...")
    t0 = time.perf_counter()
    pipeline_options = PdfPipelineOptions(
        accelerator_options=AcceleratorOptions(device=device, num_threads=8),
        ocr_options=RapidOcrOptions(backend="torch"),  # torch backend is the one that respects CUDA
    )
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    logger.info("Converter ready in %.1fs", time.perf_counter() - t0)

    results: list[dict] = []
    for pdf in pdfs:
        logger.info("Parsing: %s  (%.1f KB)", pdf.name, pdf.stat().st_size / 1024)
        t_start = time.perf_counter()
        try:
            result = converter.convert(str(pdf))
            md: str = result.document.export_to_markdown()
            elapsed = time.perf_counter() - t_start

            out_path = OUTPUT_DIR / (pdf.stem + ".md")
            out_path.write_text(md, encoding="utf-8")
            word_count = len(md.split())
            logger.info(
                "  OK  %s -> %s  (%d words, %.1fs)",
                pdf.name, out_path.name, word_count, elapsed,
            )
            results.append({
                "file": pdf.name, "status": "ok",
                "words": word_count, "seconds": round(elapsed, 1),
            })
        except Exception as exc:
            elapsed = time.perf_counter() - t_start
            logger.error("  FAIL  %s  after %.1fs: %s", pdf.name, elapsed, exc, exc_info=True)
            results.append({
                "file": pdf.name, "status": "failed",
                "error": str(exc), "seconds": round(elapsed, 1),
            })

    # --- Summary table ---
    summary_path = OUTPUT_DIR / "_summary.md"
    lines = [
        "# Docling parse summary\n\n",
        f"Device: **{device}**\n\n",
        "| File | Status | Words | Time (s) | Notes |\n",
        "|---|---|---|---|---|\n",
    ]
    for r in results:
        if r["status"] == "ok":
            lines.append(f"| {r['file']} | OK | {r['words']} | {r['seconds']} | |\n")
        else:
            lines.append(f"| {r['file']} | FAILED | - | {r['seconds']} | {r.get('error','')[:100]} |\n")
    summary_path.write_text("".join(lines), encoding="utf-8")

    ok = sum(1 for r in results if r["status"] == "ok")
    logger.info("Done - %d/%d parsed OK. Outputs: %s", ok, len(results), OUTPUT_DIR)


if __name__ == "__main__":
    main()