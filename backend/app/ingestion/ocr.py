"""Stage 0 (Priority 1) - OCR and layout parsing.

Owner: P1
"""
import logging
import os
import time

# MUST be set before any torch/docling import to disable torch.compile graph capture
# which otherwise requires Triton (no reliable Windows support).
os.environ["TORCHDYNAMO_DISABLE"] = "1"

from app.config import get_settings

logger = logging.getLogger(__name__)


def resolve_device(device_setting: str):
    """Pick the accelerator device. Returns an AcceleratorDevice enum value."""
    from docling.datamodel.accelerator_options import AcceleratorDevice
    try:
        import torch
        if device_setting == "cpu":
            logger.info("Device forced to CPU.")
            return AcceleratorDevice.CPU
        if device_setting == "cuda" or (device_setting == "auto" and torch.cuda.is_available()):
            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                logger.info("CUDA available - using GPU: %s", name)
                return AcceleratorDevice.CUDA
            else:
                logger.warning("CUDA requested but not available. Falling back to CPU.")
                return AcceleratorDevice.CPU
        
        logger.info("CUDA not available or auto selected CPU. Using CPU.")
        return AcceleratorDevice.CPU
    except ImportError:
        logger.warning("torch not installed - defaulting to CPU.")
        return AcceleratorDevice.CPU


def parse_document(file_path: str, device: str = "auto") -> str:
    """Parse a PDF document into structured markdown using Docling.
    
    Args:
        file_path: The absolute or relative path to the PDF file.
        device: 'auto', 'cuda', or 'cpu'. If 'auto', detects based on config and torch.
    
    Returns:
        Structured markdown string.
    """
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
    from docling.datamodel.accelerator_options import AcceleratorOptions
    
    resolved_device = resolve_device(device)
    
    logger.info("Building Docling converter (RapidOCR torch backend) for %s ...", file_path)
    t0 = time.perf_counter()
    
    try:
        pipeline_options = PdfPipelineOptions(
            accelerator_options=AcceleratorOptions(device=resolved_device, num_threads=8),
            ocr_options=RapidOcrOptions(backend="torch"),
        )
        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )
        logger.info("Converter ready in %.1fs", time.perf_counter() - t0)
        
        logger.info("Parsing: %s", file_path)
        t_start = time.perf_counter()
        result = converter.convert(file_path)
        md: str = result.document.export_to_markdown()
        
        elapsed = time.perf_counter() - t_start
        word_count = len(md.split())
        logger.info("Finished parsing %s in %.1fs (%d words)", file_path, elapsed, word_count)
        
        return md
    except Exception as exc:
        logger.error("Error parsing document %s: %s", file_path, exc, exc_info=True)
        raise
