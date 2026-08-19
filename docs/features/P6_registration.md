# Registration & Onboarding

**Owner:** P6
**Stage:** N/A (cross-cutting auth layer)
**Priority:** 1
**Files:**
- `backend/app/auth/router.py`
- `backend/app/auth/schemas.py` (Temporary location)
- `frontend/src/auth/Register.tsx`
- `frontend/src/auth/Login.tsx`

## What it does

Implements the end-to-end registration flow for both new Enterprises (Institutions) and new Users (Members). 

- **Enterprise Registration:** Accepts an institution name, admin email, and admin password. Creates a new `Enterprise` and the first `User` with the `admin` role.
- **User Registration:** Accepts a `tenant_code` (Institution Name), email, and password. Looks up the `Enterprise` by name and creates a new `User` with the `member` role.
- **Frontend UI:** Provides a tabbed interface to switch between "Join Institution" and "Register Institution". It uses the Claude-inspired design system to match the Login page.

## Workarounds & Follow-ups

To strictly respect the project's file ownership rules, P6 implemented this feature using temporary workarounds.

**P2 Follow-up:**
1. **Database Constraints:** The `/auth/register/enterprise` endpoint manually enforces uniqueness on `Enterprise.name`. P2 must add `unique=True` to the SQLAlchemy model and generate an Alembic migration.

**P7 Follow-up:** 
1. **API Client:** Move the `fetch` calls to `frontend/src/api/client.ts` and types to `frontend/src/chat/types.ts`.
2. **Routing:** Update `App.tsx` to handle a dedicated `/register` route (removing the temporary `view` state in `Login.tsx`).

## Example API Payloads

**POST /auth/register/enterprise**
```json
{
  "enterprise_name": "Acme Corp",
  "admin_email": "admin@acme.com",
  "admin_password": "secure123"
}
```

**POST /auth/register/user**
```json
{
  "tenant_code": "Acme Corp",
  "email": "member@acme.com",
  "password": "secure123"
}
```

Both endpoints return a standard `LoginResponse` containing the `access_token`, `tenant_id`, `user_id`, and `role`.

## Fallback behavior
- **Duplicate Names:** If an enterprise name or email already exists, the backend returns a 400 Bad Request with an explicit error message, which the frontend displays in a red warning banner.
- **Unknown Institution:** If a user tries to join an institution that doesn't exist, the backend returns a 400 Bad Request.

## Status
Done. Backend tests passing. Frontend builds without type errors.
