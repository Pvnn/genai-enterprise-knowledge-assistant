# Conversation Threads & Chat History API

**Owner:** P2  
**Endpoints:** `/conversations`  
**Priority:** 1  
**Files:**
- `backend/app/conversations/router.py`
- `backend/app/models.py` (`Conversation`, `Message`)
- `backend/app/schemas.py` (`ConversationCreate`, `ConversationUpdate`, `ConversationSummary`, `ConversationDetail`, `MessageCreate`, `MessageResponse`)
- `backend/db/migrations/versions/a1b2c3d4e5f6_initial_schema.py`
- `backend/tests/test_conversations.py`

## What it does

Provides cloud-persisted, cross-device multi-turn conversation threads and message history for the ChatGPT/Gemini-style sidebar UI.

### Tenant & User Isolation Guarantee
All endpoints enforce strict isolation:
- Queries filter on both `Conversation.tenant_id == current_user.tenant_id` and `Conversation.user_id == current_user.user_id`.
- A user cannot list, inspect, rename, or delete another user's conversation threads or threads from another tenant.

---

## API Endpoints

### 1. `GET /conversations` — List Conversation Threads
Returns all conversation summaries for the authenticated user, ordered by `updated_at DESC`.

**Response (HTTP 200):**
```json
[
  {
    "id": "b791f9b6-392f-4cd2-81ac-598d84c8e6fd",
    "title": "Leave Policy Inquiry",
    "created_at": "2026-08-19T20:00:00",
    "updated_at": "2026-08-19T20:05:00",
    "message_count": 4
  }
]
```

### 2. `POST /conversations` — Create Conversation Thread
Creates a new conversation thread for the authenticated user.

**Request:**
```json
{
  "title": "Medical Insurance Q&A"
}
```

**Response (HTTP 201):**
```json
{
  "id": "b791f9b6-392f-4cd2-81ac-598d84c8e6fd",
  "title": "Medical Insurance Q&A",
  "created_at": "2026-08-19T20:00:00",
  "updated_at": "2026-08-19T20:00:00",
  "message_count": 0
}
```

### 3. `GET /conversations/{conversation_id}` — Get Conversation Detail
Fetches the full conversation thread with all user and assistant messages sorted chronologically.

**Response (HTTP 200):**
```json
{
  "id": "b791f9b6-392f-4cd2-81ac-598d84c8e6fd",
  "title": "Medical Insurance Q&A",
  "created_at": "2026-08-19T20:00:00",
  "updated_at": "2026-08-19T20:05:00",
  "messages": [
    {
      "id": "01bb1fae-8d94-4365-8074-737263da6d99",
      "conversation_id": "b791f9b6-392f-4cd2-81ac-598d84c8e6fd",
      "role": "user",
      "content": "What is the insurance coverage limit?",
      "citations": null,
      "confidence": null,
      "refused": false,
      "refusal_reason": null,
      "created_at": "2026-08-19T20:00:05"
    },
    {
      "id": "90718a70-5aff-4f60-8933-31802f1354e9",
      "conversation_id": "b791f9b6-392f-4cd2-81ac-598d84c8e6fd",
      "role": "assistant",
      "content": "The standard policy covers up to $500,000 per year.",
      "citations": [
        {
          "chunk_id": "09872830-61dc-42dc-ba89-6103ef3639f1",
          "document_id": "ad45fd47-f2fa-4a40-b48d-0802a83968e3",
          "text": "Medical coverage ceiling is $500,000.",
          "section_path": "3.1 Coverage Limits",
          "score": 0.95
        }
      ],
      "confidence": 0.95,
      "refused": false,
      "refusal_reason": null,
      "created_at": "2026-08-19T20:00:10"
    }
  ]
}
```

### 4. `PATCH /conversations/{conversation_id}` — Rename Conversation
Renames the title of a conversation thread.

**Request:**
```json
{
  "title": "Health & Medical Policy"
}
```

**Response (HTTP 200):**
```json
{
  "id": "b791f9b6-392f-4cd2-81ac-598d84c8e6fd",
  "title": "Health & Medical Policy",
  "created_at": "2026-08-19T20:00:00",
  "updated_at": "2026-08-19T20:06:00",
  "message_count": 2
}
```

### 5. `DELETE /conversations/{conversation_id}` — Delete Conversation
Deletes a conversation thread and cascades deletion to all its messages.

**Response (HTTP 200):**
```json
{
  "status": "deleted",
  "id": "b791f9b6-392f-4cd2-81ac-598d84c8e6fd"
}
```

### 6. `POST /conversations/{conversation_id}/messages` — Append Message
Appends a message to a conversation thread and updates `updated_at`.

**Request:**
```json
{
  "role": "user",
  "content": "Can family members be added to the plan?"
}
```

**Response (HTTP 201):**
```json
{
  "id": "4b684964-1a61-4200-84c4-7225c567c9c0",
  "conversation_id": "b791f9b6-392f-4cd2-81ac-598d84c8e6fd",
  "role": "user",
  "content": "Can family members be added to the plan?",
  "citations": null,
  "confidence": null,
  "refused": false,
  "refusal_reason": null,
  "created_at": "2026-08-19T20:07:00"
}
```

---

## Status
Done & Verified on SQLite in-memory tests and live Neon PostgreSQL database.
