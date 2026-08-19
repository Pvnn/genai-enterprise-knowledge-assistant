# Chat UI and SSE Streaming

**Owner:** P7
**Stage:** 5
**Priority:** 1
**Files:** `frontend/src/chat/ChatPage.tsx`, `frontend/src/chat/ChatMessageItem.tsx`, `frontend/src/chat/CitationCard.tsx`, `frontend/src/chat/RefusalBanner.tsx`, `frontend/src/chat/ConflictAlert.tsx`, `frontend/src/chat/ClarifyPrompt.tsx`, `frontend/src/chat/types.ts`, `frontend/src/api/client.ts`, `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/index.css`

## What it does

Implements the user-facing web chat interface for the GenAI Enterprise Knowledge Assistant. It streams server-sent events (SSE) from `POST /chat`, rendering live token generation, interactive clarifying questions when context is ambiguous, low-confidence refusal banners with guidance, dual-surfaced version conflict warnings, and clickable grounded citations.

## Example

**Input:** User query `"What is the maternity leave entitlement for faculty?"` with `tenant_id: "00000000-0000-0000-0000-000000000001"`.
**Output:** Streamed token response with grounded citations rendered as chips `[Leave Policy 2025, Section 3.2.2]` linking to source documents, or a refusal banner if retrieval confidence is below 0.70.

## Depends on / called by

Depends on:
- `POST /chat` endpoint exposed by P4 (`generation/router.py`) streaming SSE events (`token`, `clarify`, `final`).
- `GET /auth/me` and `POST /auth/login` exposed by P6 (`auth/router.py`).

Called by:
- End users accessing the web application via modern desktop or mobile browsers.

## Fallback behavior

N/A - no fallback, this is the spine.

## Status

Done

## Known issues / open questions

- **Auth context & logout integration:** P7 has provided the Logout UI button and action hook in `ChatSidebar.tsx` and `App.tsx`. P6 owns authentication (`frontend/src/auth/*`) and needs to export an auth provider / hook (e.g. `useAuth().logout()`) that manages session state, token invalidation, and auth redirect.
- **query_id schema gap:** `query_id` is required by `POST /feedback` (Section 5) but is omitted from the `FinalEvent` schema in `POST /chat`. This schema gap is owned by P2 (`schemas.py`) and P4 (`generator.py` / `/chat` router). The frontend uses a temporary local message-bound ID placeholder pending backend confirmation.
- **Unconfirmed conflict shape:** The internal structure of the `conflict` field/event is not fully specified in Section 6. The `ConflictAlert` component has been built defensively to handle raw text answers and optional citation lists without rigid structural assumptions.

## Tests

- `frontend/src/tests/client.test.ts` (testing `streamChat` SSE token, clarify, final events, and forward-compatibility with unknown event types).
- `frontend/src/tests/ConflictAlert.test.tsx` (testing well-formed rendering and graceful degradation when conflict is unconfirmed, null, or undefined).
- `npm test` (14/14 tests passing).
- `npm run build` and `npm run lint` (0 errors, 0 warnings).

