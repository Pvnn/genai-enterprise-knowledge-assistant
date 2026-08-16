"""Generation router – exposes POST /chat (SSE streaming).

Owner: P4
See Section 5 for the exact SSE event contract:
  - token events while generating
  - clarify event if needs_clarification (Priority 2)
  - final event with answer, citations, confidence, refused, conflict
"""

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.deps import CurrentUserDep, DbDep
from app.generation.generator import generate_answer
from app.schemas import ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    db: DbDep,
    current_user: CurrentUserDep,
) -> StreamingResponse:
    """Stream a grounded answer to a user query over Server-Sent Events."""

    async def event_stream():
        async for event in generate_answer(request, db):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
