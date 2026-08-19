# P6 Stage 5 Feedback Endpoint

**Owner:** P6
**Stage:** 5
**Priority:** 2
**Files:** `backend/app/auth/router.py`, `backend/tests/test_auth.py`

## What it does

This feature exposes a `POST /auth/feedback` endpoint that allows authenticated users to submit a thumbs-up or thumbs-down rating and an optional comment on a generated answer. It provides the crucial data needed to monitor generation quality and user satisfaction in the system.

*(Note: While the spec lists this as `POST /feedback`, it is mounted under the P6-owned `auth/router.py` prefix as `/auth/feedback`. If the team wants it on the root URL, P2 can remount the route in `main.py` without code changes here.)*

## Example

**Input:**
```json
{
  "query_id": "01267269-54ec-49ab-9a16-9dc59cd40f65",
  "thumbs_up_down": true,
  "comment": "This accurately summarized the leave policy."
}
```

**Output:**
```json
{
  "status": "ok"
}
```

## Depends on / called by

*   **Depends on:** P2's `Feedback` and `Query` ORM models from `backend/app/models.py`.
*   **Called by:** P7's frontend chat interface (Feedback buttons UI).

## Fallback behavior

N/A — if the endpoint goes down, the frontend feedback buttons simply fail to save the user's vote. It does not break the core Priority 1 retrieval or generation pipeline.

## Status

Done.

## Known issues / open questions

*   The endpoint is currently mounted at `/auth/feedback` because P6 owns the auth router. P2 may want to remount this route if they prefer `/feedback` at the top level.

## Tests

`backend/tests/test_auth.py` (see `test_submit_feedback_success` and `test_submit_feedback_unauthorized`).
