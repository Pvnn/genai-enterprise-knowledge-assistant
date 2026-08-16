"""Stage 5 – Grounded answer generation and full pipeline orchestration.

Owner: P4  |  Priority: 1
This file is the single orchestration point for the entire query pipeline.
The call order is specified in Section 6 of the engineering spec:

  1. query_rewriter.rewrite()       [P2 fallback: raw query]
  2. routing.route_query()          [Priority 2; fallback: scoped_sections=None]
  3. dense_retrieval.retrieve_chunks() + hybrid_retrieval (Priority 2)
  4. reranker.rerank()              [Priority 2; fallback: first top_n]
  5. Merge sub-query results
  6. Draft answer via LLM with inline citations
  7. grounding.decide_refusal()     [which calls conflict_detector internally]
  8. Stream the final SSE response

Every Priority 2 step is wrapped in a try/except that falls back to the
Priority 1 behavior rather than crashing the request.
"""

import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import ChatRequest, ChunkResult, FinalEvent

logger = logging.getLogger(__name__)


async def generate_answer(
    request: ChatRequest,
    session: AsyncSession,
) -> AsyncGenerator[dict, None]:
    """Orchestrate the full RAG pipeline and stream SSE events.

    Args:
        request: The validated chat request (query, tenant_id, conversation_id).
        session: Async database session.

    Yields:
        dict: SSE event dicts – one of TokenEvent, ClarifyEvent, or FinalEvent
              shapes as defined in app.schemas.
    """
    raise NotImplementedError("P4: implement generate_answer() in generator.py")
