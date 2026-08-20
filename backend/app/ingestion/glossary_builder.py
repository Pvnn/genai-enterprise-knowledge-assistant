"""Stage 0, Priority 2 - Acronym / entity glossary builder.

Owner: P1  |  Priority: 2
Auto-builds a corpus-wide acronym/entity glossary and stores it in the
glossary table.  Used by Stage 1 query rewriting (P4) for acronym expansion.
"""

import logging
import re

logger = logging.getLogger(__name__)

def is_subsequence(sub: str, full: str) -> bool:
    """Check if characters of sub appear in order in full."""
    it = iter(full)
    return all(c in it for c in sub)

def clean_expansion(text: str) -> str:
    """Normalize whitespace and strip common leading stopwords."""
    text = re.sub(r'\s+', ' ', text).strip()
    stopwords = ["the ", "a ", "an ", "using ", "for ", "with ", "in ", "of ", "and "]
    lower_text = text.lower()
    for sw in stopwords:
        if lower_text.startswith(sw):
            text = text[len(sw):]
            lower_text = lower_text[len(sw):]
    return text.strip()

def is_valid_acronym_match(term: str, expansion: str) -> bool:
    """Validate the acronym against the expansion using heuristics."""
    if not (2 <= len(term) <= 8):
        return False
    if term.upper() == expansion.upper():
        return False
        
    # Extract initials of significant words in the expansion
    words = [w for w in re.split(r'\W+', expansion) if w]
    initials = "".join([w[0].upper() for w in words if w])
    
    term_upper = term.upper()
    
    # Exact initials match
    if term_upper == initials:
        return True
        
    # Subsequence alignment check
    # Check if term characters appear in order in the initials
    if is_subsequence(term_upper, initials):
        # Allow if match ratio is decent or if it's a known format
        return True
        
    # If not a subsequence of initials, check if it's a subsequence of the full expansion
    # For example, "HNSW" in "Hierarchical Navigable Small World"
    if is_subsequence(term_upper, expansion.upper()):
        return True

    return False

async def build_glossary(tenant_id: str, chunks: list[dict]) -> list[dict]:
    """Build or update the acronym/entity glossary from ingested chunks using regex heuristics.

    Args:
        tenant_id: The tenant whose corpus is being indexed.
        chunks: List of chunk dicts (must include text field).

    Returns:
        list[dict]: List of glossary entries.
    """
    entries_map = {}
    
    # Regex patterns
    # Pattern 1: Full Expansion (ACRONYM)
    pat1 = re.compile(r'\b((?:(?:[A-Z][a-z0-9\-]+|[a-z]{1,4})\s+){1,6}[A-Z][a-z0-9\-]+)\s*\(([A-Z0-9]{2,8})\)')
    # Pattern 2: ACRONYM (Full Expansion)
    pat2 = re.compile(r'\b([A-Z0-9]{2,8})\s*\(([A-Z][A-Za-z0-9\-,\s]{5,70})\)')

    for c in chunks:
        text = c.get("text", "") if isinstance(c, dict) else getattr(c, "text", "")
        
        for match in pat1.finditer(text):
            expansion, term = match.groups()
            term = term.strip()
            expansion = clean_expansion(expansion)
            if is_valid_acronym_match(term, expansion):
                entries_map[term] = expansion
                
        for match in pat2.finditer(text):
            term, expansion = match.groups()
            term = term.strip()
            expansion = clean_expansion(expansion)
            if term not in entries_map and is_valid_acronym_match(term, expansion):
                entries_map[term] = expansion

    valid_entries = [{"term": t, "expansion": e} for t, e in entries_map.items()]
    logger.info(f"Extracted {len(valid_entries)} glossary entries via regex.")
    return valid_entries
