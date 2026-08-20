# Citations Side Panel & Auto-scrolling

**Owner:** P7
**Stage:** 5
**Priority:** 1
**Files:** rontend/src/chat/DocumentSidePanel.tsx, rontend/src/chat/ChatPage.tsx, rontend/src/chat/CitationCard.tsx, rontend/src/chat/ChatMessageItem.tsx, rontend/src/chat/types.ts, rontend/src/api/client.ts

## What it does

Implements an interactive document side-panel viewer for grounded citations. When a user clicks a citation in a chat response, the layout smoothly shifts to accommodate a sliding panel on the right. This panel fetches the full raw markdown document from the object storage backend, renders it natively using eact-markdown, and utilizes a robust DOM traversal algorithm to accurately fuzzy-match the cited chunk, highlighting it in a gold accent and scrolling it securely into the center of the viewport to provide transparent source verification.

## Example

**Input:** User clicks on a citation chip in the CitationCard below a grounded response.
**Output:** The ChatPage flex layout resizes the main chat to 7/12 width, the DocumentSidePanel mounts in the remaining 5/12 width, loads the raw markdown of the document, normalizes the chunk text, identifies the highest-matching prefix block element (e.g. p, li, 	d) among all rendered DOM nodes, applies a gold background fade, and executes scrollIntoView({ behavior: 'smooth', block: 'center' }).

## Depends on / called by

Depends on:
- GET /documents/{document_id}/content backend endpoint returning raw markdown content from Object Storage (Neon / S3).
- The inal_payload's Citation schema returning the raw chunk 	ext alongside chunk_id and document_id (added to backend in this feature).

Called by:
- End users clicking a citation pill in the Chat UI.

## Fallback behavior

The highlighting and auto-scroll feature has multiple built-in fallbacks to combat discrepancies between chunk boundaries and markdown HTML rendering:
1. **Normalization:** Strips all non-alphanumeric characters to ignore markdown artifacts like **bolding** splitting text nodes.
2. **Descending Prefix Matching:** Checks descending prefix lengths of the citation text against the rendered HTML blocks to capture chunks that start mid-sentence or contain broken formatting.
3. **Substring Encompassment:** If prefix matching fails entirely, the algorithm checks if any fully-rendered block element is contained entirely *within* the citation text, allowing it to anchor onto internal paragraphs.
4. **Final Fallback:** If all highlighting matching strategies fail, the document is simply rendered at the top of the viewport for manual review.

## Status

Done

## Known issues / open questions

- **Performance:** Very large documents (e.g., thousands of lines of markdown) might cause slight stuttering when eact-markdown initially parses and renders them to the DOM. The setTimeout delays the heavy DOM traversal search by 500ms to allow rendering to complete safely.

## Tests

- Tested manually using large markdown documents and edge-case chunk boundaries (mid-sentence chunking, table elements, bullet points).
- Built cleanly with zero ESLint/TypeScript errors via 
pm run lint.
