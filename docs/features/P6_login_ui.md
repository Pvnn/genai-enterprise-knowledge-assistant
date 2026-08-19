# Login UI — Authentication Page

**Owner:** P6
**Stage:** N/A (auth entry-point — gates all other pages)
**Priority:** 1
**Files:**
- `frontend/src/auth/Login.tsx`

## What it does

Renders the Login page at `/login`. Collects institution name (`tenant_code`),
email, and password; calls `POST /auth/login` via the existing `login()` helper
in `api/client.ts`; stores the returned JWT, tenant ID, user ID, and role in
`localStorage`; then navigates to `/chat`. Also guards against already-authenticated
users landing on `/login` — they are immediately redirected to `/chat`.

## Design

Matches the rest of the app's Claude-inspired palette (Civic Indigo, Warm Paper,
Deep Slate). Uses CSS custom properties from `index.css` and Tailwind utility
classes. Icons from `@phosphor-icons/react`. Dark mode supported via the `.dark`
class applied by P7's `ChatPage`.

## Example flow

```
User opens /login
  └─ Has access_token in localStorage?
       ├─ Yes → replaceState to /chat immediately
       └─ No  → show login form
            └─ submit: POST /auth/login
                 ├─ 200 → store token/tenant/role → pushState /chat
                 └─ 4xx → show inline error banner (red, with WarningCircle icon)
```

**POST /auth/login request:**
```json
{ "email": "admin@acme.com", "password": "secret", "tenant_code": "Acme University" }
```
**POST /auth/login response → stored to localStorage:**
```
localStorage["access_token"] = "eyJ..."
localStorage["tenant_id"]    = "uuid"
localStorage["user_id"]      = "uuid"
localStorage["user_role"]    = "admin"
```

## Depends on / called by

| Direction | Module |
|---|---|
| Calls | `api/client.ts → login()` — wraps `POST /auth/login` (P7) |
| Calls | `chat/types.ts → LoginRequest, LoginResponse` — shared type defs (P7) |
| Called by | `App.tsx` — renders `<Login />` when `currentPath === "/login"` (P7) |
| Reads/writes | `localStorage` — same keys as `App.tsx` and `ChatPage.tsx` |

## localStorage keys

| Key | Value | Consumer |
|---|---|---|
| `access_token` | JWT string | `api/client.ts getAuthHeader()`, `App.tsx` logout |
| `tenant_id` | UUID string | `ChatPage.tsx` |
| `user_id` | UUID string | available for future use |
| `user_role` | `"admin"` \| `"member"` | `App.tsx` upload guard |

## Fallback behavior

- Empty field validation runs client-side before any network request.
- If `POST /auth/login` returns 4xx, the error `detail` from the JSON envelope
  is shown inline. Network failures show a generic fallback message.
- Show/hide password toggle for usability.
- Button and inputs are disabled with reduced opacity while the request is in flight.

## Status

Done — `tsc && vite build` passes with zero errors.

## Known issues / open questions

- **Back-button bypass:** After logout, the browser history still contains `/chat`.
  Pressing Back navigates there without a token. `Login.tsx` redirects already-logged-in
  users away from `/login`, but the inverse (forcing unauthenticated users to `/login`
  from any route) requires an auth guard in `App.tsx` (P7's file). Flag to P7:
  ```tsx
  // App.tsx — add before route checks:
  if (currentPath !== "/login" && !localStorage.getItem("access_token")) {
    window.history.replaceState({}, "", "/login");
    return <Login />;
  }
  ```
- **Institution field UX:** `tenant_code` is a free-text field matching
  `enterprises.name` case-insensitively. If the team later wants a short slug
  (e.g. `acme`) instead of the full name, P2 needs to add a slug column and
  migration, and P6 can update the label/placeholder accordingly.

## Tests

Frontend unit tests are in `frontend/src/tests/`. Login.tsx relies on
`api/client.ts → login()` which can be mocked in a Vitest/React Testing Library
test. Integration testing is covered end-to-end by the running stack (Neon DB +
uvicorn + Vite).
