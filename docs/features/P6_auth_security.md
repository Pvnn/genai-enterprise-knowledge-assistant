# Auth — JWT Security, Login & Tenant Scoping

**Owner:** P6
**Stage:** N/A (cross-cutting auth layer — gates Stages 0–5)
**Priority:** 1
**Files:**
- `backend/app/auth/security.py`
- `backend/app/auth/tenancy.py`
- `backend/app/auth/router.py`

## What it does

Provides the full authentication layer for the system: JWT token creation
and validation (`security.py`), enterprise tenant resolution by name
(`tenancy.py`), and the three auth HTTP endpoints (`router.py`). Every
protected endpoint in the system — document upload (P1), retrieval (P2),
and chat (P4) — goes through `get_current_user()` via P2's `CurrentUserDep`
before any stage logic runs.

## Example

**Input (POST /auth/login):**
```json
{ "email": "admin@acme.com", "password": "secret", "tenant_code": "Acme University" }
```
**Output:**
```json
{ "access_token": "eyJ...", "tenant_id": "uuid", "user_id": "uuid", "role": "admin" }
```

**Input (GET /auth/me — Authorization: Bearer eyJ...):**
```json
{ "user_id": "uuid", "tenant_id": "uuid", "email": "admin@acme.com", "role": "admin" }
```

## Depends on / called by

| Direction | Module |
|---|---|
| Calls | `app.auth.models.Enterprise`, `app.auth.models.User` (P6 — already done) |
| Calls | `app.config.get_settings()` — jwt_secret_key, jwt_algorithm, expire_minutes (P2) |
| Calls | `app.database.get_db` — async session factory (P2) |
| Calls | `app.schemas.CurrentUser`, `LoginRequest`, `LoginResponse`, etc. (P2) |
| Called by | `app.deps.CurrentUserDep` (P2) — all protected routes use this |
| Called by | `app.auth.router.login()` — `create_access_token` called on successful login |

## Fallback behavior

N/A — Priority 1, no fallback. This is the spine of all authentication.
If `get_current_user` raises, FastAPI returns 401 and the request stops.

## Status

Done

## Known issues / open questions

- `get_current_user` adds `session: AsyncSession = Depends(get_db)` as a
  second FastAPI dependency. This is invisible to callers and consistent
  with the spec contract (`get_current_user(token) -> CurrentUser`). The
  DB lookup confirms the user still exists on every request — one extra
  round-trip per request for security.
- `POST /auth/feedback` uses a raw `text()` SQL insert because the
  `Feedback` ORM class is not yet in `app/models.py` (P2's file). The
  table IS created by the Alembic migration. Flag to P2 to add the ORM
  class so this can be cleaned up later.
- `tenant_code` is matched case-insensitively against `enterprises.name`.
  There is no separate short-code column in the schema. Flag to the team
  if a dedicated slug/code column is preferred — would require P2 to add
  a migration column.

## Tests

`backend/tests/test_auth.py` — to be written (stubs exist).
