# Answer Feedback and UI Polish

**Owner:** P7
**Stage:** 5
**Priority:** 2
**Files:** `frontend/src/chat/FeedbackModal.tsx`, `frontend/src/chat/ChatSidebar.tsx`, `frontend/src/chat/ChatMessageItem.tsx`, `frontend/src/chat/ChatPage.tsx`, `frontend/src/api/client.ts`

## What it does

Provides interactive thumbs up / thumbs down feedback controls on generated assistant responses, allowing users to submit qualitative commentary (e.g., outdated policy circulars, incorrect section references) to `POST /feedback`. Also provides conversation thread management, prompt starters, dark/light theme switching, responsive mobile layouts, and tactile micro-interactions.

## Example

**Input:** User clicks thumbs-down on an answer and inputs `"Section 3.2 was amended by Circular 44 in 2024"`.
**Output:** Submits `{ query_id: "<placeholder_id>", thumbs_up_down: false, comment: "Section 3.2 was amended by Circular 44 in 2024" }` to `POST /feedback` and displays confirmation.

## Depends on / called by

Depends on:
- `POST /feedback` endpoint exposed by P6 (`auth/router.py`).

Called by:
- End users rating answer accuracy or reporting discrepancies.

## Fallback behavior

If `POST /feedback` fails or is unavailable on the backend, an inline non-blocking error alert informs the user without interrupting the active chat session.

## Status

Done

## Known issues / open questions

- **query_id schema gap:** `query_id` is required by `POST /feedback` (Section 5) but is omitted from the `FinalEvent` schema in `POST /chat`. This schema gap is owned by P2 (`schemas.py`) and P4 (`generator.py` / `/chat` router). The frontend uses a temporary local message-bound ID placeholder pending backend confirmation.
- **Unconfirmed conflict shape:** The internal structure of the `conflict` field/event is not fully specified in Section 6. The frontend components defensively parse conflict payloads to prevent breaking changes when backend shapes are finalized.

## Tests

- `frontend/src/tests/FeedbackModal.test.tsx` (testing `FeedbackModal` rendering, submission shape, and `query_id` placeholder logic).
- `frontend/src/tests/client.test.ts` (testing `submitFeedback` endpoint shape).
- `npm test` (14/14 tests passing).
- `npm run build` and `npm run lint` (0 errors, 0 warnings).

