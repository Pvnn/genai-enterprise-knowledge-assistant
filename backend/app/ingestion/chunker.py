"""Stage 0 (Priority 1) - Heading-aware chunking.

Owner: P1
"""
import logging
import re

logger = logging.getLogger(__name__)

# Typical embedding models handle ~512-8192 tokens. 
# We aim for ~1000-1500 chars per chunk to provide good granularity 
# while keeping enough context.
TARGET_CHUNK_SIZE = 1200  


def chunk_document(markdown_text: str) -> list[dict]:
    """Chunk a markdown document into smaller segments while preserving heading paths.
    
    Args:
        markdown_text: The full markdown string returned by the OCR step.
        
    Returns:
        A list of dictionaries, each containing:
            - "text": The chunk's text content.
            - "section_path": The hierarchical heading path (e.g., "Heading 1 / Subheading 2").
    """
    chunks = []
    
    # Maintain a stack of headings: [(level, title)]
    heading_stack: list[tuple[int, str]] = []
    
    current_chunk_text = []
    current_chunk_len = 0
    current_section_path = "Document Start"
    
    # Only track explicit Markdown ATX headings in the section_path
    ATX_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$')
    # Structural markers still trigger a block flush (paragraphs, lists, etc.) so we don't break mid-clause
    STRUCTURAL_MARKER_RE = re.compile(r'^(#{1,6}\s+|\d+\.\s+|- |\* |[a-zA-Z]\.\s+|\d+\.\d+\s+)')
    
    def _flush_chunk():
        nonlocal current_chunk_text, current_chunk_len
        if current_chunk_text:
            text = "\n\n".join(current_chunk_text).strip()
            if text:
                chunks.append({
                    "text": text,
                    "section_path": current_section_path
                })
            current_chunk_text = []
            current_chunk_len = 0

    lines = markdown_text.split('\n')
    current_block_lines = []
    
    def _flush_block():
        nonlocal current_chunk_text, current_chunk_len, current_section_path, heading_stack
        if not current_block_lines:
            return
            
        block = "\n".join(current_block_lines).strip()
        current_block_lines.clear()
        if not block:
            return
            
        first_line = block.split('\n')[0].strip()
        
        atx_match = ATX_HEADING_RE.match(first_line)
        
        if atx_match:
            _flush_chunk()
            
            level = len(atx_match.group(1))
            title = atx_match.group(2).strip()
                
            heading_stack = [h for h in heading_stack if h[0] < level]
            heading_stack.append((level, title))
            current_section_path = " / ".join([h[1] for h in heading_stack])
            
            current_chunk_text.append(block)
            current_chunk_len += len(block)
        else:
            if current_chunk_text and current_chunk_len + len(block) > TARGET_CHUNK_SIZE:
                _flush_chunk()
            
            current_chunk_text.append(block)
            current_chunk_len += len(block)

    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            if current_block_lines:
                current_block_lines.append(line)
            continue
            
        if STRUCTURAL_MARKER_RE.match(stripped_line) and current_block_lines:
            _flush_block()
            
        current_block_lines.append(line)
        
    _flush_block()
    _flush_chunk()
    
    logger.info("Chunked document into %d pieces", len(chunks))
    return chunks
