"""Stage 0, Priority 2 – Section-tree (heading hierarchy) extraction.

Owner: P1  |  Priority: 2
Extracts the heading hierarchy from a structured-markdown document and stores
it as JSONB in documents.section_tree.  Used by Stage 2b LLM section routing.
Fallback: if this module is unavailable, scoped_sections is None and retrieval
searches the full tenant corpus.
"""

import logging

logger = logging.getLogger(__name__)

import re

ATX_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$')
ENUM_TITLE_RE = re.compile(r'^(\d+|[A-Z])[\.\)]\s')

def _enum_kind(title: str) -> str | None:
    m = ENUM_TITLE_RE.match(title)
    if not m:
        return None
    return 'digit' if m.group(1).isdigit() else 'letter'

def extract_section_tree(markdown: str) -> list[dict]:
    lines = markdown.split('\n')
    tokens = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = ATX_HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            tokens.append({
                "type": "heading",
                "level": level,
                "title": title,
                "enum_kind": _enum_kind(title),  # None | 'digit' | 'letter'
                "valid": True,
            })
        else:
            tokens.append({"type": "text", "content": line})

    # Invalidate an enum heading only if it's DIRECTLY adjacent (no text between)
    # to another heading of the same enum kind at the same level — that pattern
    # is a fragmented list, not real hierarchy. Pairwise, so one bad match can
    # never poison unrelated headings elsewhere in the doc.
    for i, token in enumerate(tokens):
        if token["type"] != "heading" or token["enum_kind"] is None:
            continue
        for j in (i - 1, i + 1):
            if 0 <= j < len(tokens):
                neighbor = tokens[j]
                if (neighbor["type"] == "heading"
                        and neighbor["enum_kind"] == token["enum_kind"]
                        and neighbor["level"] == token["level"]):
                    token["valid"] = False
                    break

    # 3. Build tree (unchanged)
    tree = []
    stack: list[tuple[int, dict]] = []
    for token in tokens:
        if token["type"] == "heading" and token["valid"]:
            level = token["level"]
            title = token["title"]
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent_path = stack[-1][1]["section_path"] if stack else ""
            section_path = f"{parent_path} / {title}" if parent_path else title
            node = {"title": title, "section_path": section_path, "children": []}
            if stack:
                stack[-1][1]["children"].append(node)
            else:
                tree.append(node)
            stack.append((level, node))

    return tree
