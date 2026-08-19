"""Generation router – exposes POST /chat (SSE streaming).

Owner: P4
See Section 5 for the exact SSE event contract:
  - token events while generating
  - clarify event if needs_clarification (Priority 2)
  - final event with answer, citations, confidence, refused, conflict

Tenant isolation fix (flagged per Section 0 rule 6, Section 1 NFR): the
request body's tenant_id must never be trusted on its own — a client could
put any tenant_id in the request JSON. The authenticated user's own
tenant_id (from their verified login token, via current_user) is the only
trustworthy source, so it always overrides whatever the request body said.
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

    if request.tenant_id != current_user.tenant_id:
        logger.warning(
            "tenant_id mismatch on /chat: request declared %s but authenticated user "
            "belongs to %s — overriding with the authenticated tenant_id",
            request.tenant_id,
            current_user.tenant_id,
        )
    request.tenant_id = current_user.tenant_id  # never trust the client-supplied value

    async def event_stream():
        async for event in generate_answer(request, db):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")