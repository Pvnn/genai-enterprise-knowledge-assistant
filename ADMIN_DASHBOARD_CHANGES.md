# Admin Dashboard & Integration Changes

This document lists all files created and modified for the **Admin Dashboard**, the backend admin endpoints, and the supporting pipeline fixes. Use this as a reference when pulling changes from your teammates and merging work.

---

## 1. Summary of Changes

### A. New Admin Files (Safe to commit / no conflicts with teammates)
These files were created from scratch and are self-contained.

| File | Purpose |
|---|---|
| `backend/app/admin/router.py` | FastAPI admin router implementing `/admin/analytics`, `/admin/documents`, `/admin/documents/{id}`, `/admin/documents/{id}/status`, `/admin/documents/{id}/content`, `/admin/users`, and `/admin/glossary`. |
| `backend/app/admin/__init__.py` | Package export for `admin_router`. |
| `backend/tests/test_admin.py` | 10 comprehensive pytest cases covering all admin endpoints, role checks, document cascade deletion, and multi-tenant isolation. |
| `backend/app/llm.py` | Unified LLM client factory supporting both OpenAI and Groq (`gsk_...`) endpoints and model mapping. |
| `frontend/src/admin/AdminDashboard.tsx` | Complete Admin Dashboard component with 4 tabs: Overview & Analytics, Document Management (with chunk inspector), Enterprise Members, and Glossary Management. |
| `frontend/src/admin/AdminDashboard.css` | Styling and responsive design for the Admin Dashboard. |
| `frontend/src/admin/types.ts` | TypeScript interfaces for admin analytics, documents, users, and glossary entries. |
| `frontend/src/admin/index.ts` | Component export for `AdminDashboard`. |
| `frontend/src/tests/AdminDashboard.test.tsx` | Frontend unit tests for the Admin Dashboard. |

---

### B. Modified Existing Files (Shared with teammates)
These are shared files where additions were made.

#### 1. Backend

- **[`backend/app/main.py`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/backend/app/main.py)**:
  - Registered `admin_router` with `app.include_router(admin_router, prefix="/admin", tags=["admin"])`.

- **[`backend/app/schemas.py`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/backend/app/schemas.py)**:
  - Added Pydantic schemas for the admin panel:
    - `AdminAnalyticsResponse`
    - `AdminDocumentItem`, `AdminDocumentUpdate`, `AdminChunkItem`, `AdminDocumentDetail`
    - `AdminUserItem`, `AdminUserCreate`
    - `AdminGlossaryItem`, `AdminGlossaryCreate`

- **[`backend/app/ingestion/router.py`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/backend/app/ingestion/router.py)**:
  - Added `GET /documents` endpoint so regular users in the chat workspace can view real indexed documents in the Document Library.

- **[`backend/app/config.py`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/backend/app/config.py)**:
  - Updated `sanitize_database_url` to convert `postgresql://` to `postgresql+asyncpg://`, map `sslmode` to `ssl`, and strip unsupported libpq parameters like `channel_binding`.

- **[`backend/app/auth/router.py`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/backend/app/auth/router.py)**:
  - Replaced `passlib.context.CryptContext` with direct `bcrypt` methods (`_hash_password`, `_verify_password`) to avoid passlib 72-byte truncation crash.

- **[`backend/app/generation/generator.py`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/backend/app/generation/generator.py)**:
  - Used unified `get_llm_client()` and `get_llm_model()`.
  - Fixed argument order when calling `_route_query(sub_query, tenant_id, session)`.
  - Ran synchronous `_rerank` via `asyncio.to_thread(_rerank, ...)`.

- **[`backend/app/generation/query_rewriter.py`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/backend/app/generation/query_rewriter.py)**, **[`grounding.py`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/backend/app/generation/grounding.py)**, **[`conflict_detector.py`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/backend/app/generation/conflict_detector.py)**, **[`summarizer.py`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/backend/app/ingestion/summarizer.py)**, **[`routing.py`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/backend/app/retrieval/routing.py)**:
  - Updated to use `get_llm_client()` and `get_llm_model()` for Groq/OpenAI compatibility.

- **[`backend/app/ingestion/glossary_builder.py`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/backend/app/ingestion/glossary_builder.py)**:
  - Improved acronym regex to handle lowercase connecting prepositions (e.g. `National Aeronautics and Space Administration (NASA)`).

#### 2. Frontend

- **[`frontend/src/App.tsx`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/frontend/src/App.tsx)**:
  - Added state and view toggle for switching between Chat Workspace, Document Library, and Admin Dashboard.

- **[`frontend/src/chat/ChatSidebar.tsx`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/frontend/src/chat/ChatSidebar.tsx)**:
  - Added "Admin Dashboard" navigation button with `ADMIN` badge (visible for admin role).

- **[`frontend/src/api/client.ts`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/frontend/src/api/client.ts)**:
  - Added API client methods for all admin operations (`fetchAdminAnalytics`, `fetchAdminDocuments`, `updateAdminDocument`, `deleteAdminDocument`, `fetchAdminDocumentDetail`, `fetchAdminUsers`, `createAdminUser`, `deleteAdminUser`, `fetchAdminGlossary`, `createAdminGlossary`, `deleteAdminGlossary`).

- **[`frontend/src/chat/types.ts`](file:///Users/karthikjayan/genai-enterprise-knowledge-assistant/frontend/src/chat/types.ts)**:
  - Added `token_type?: string` to `LoginResponse`.

---

## 2. Recommended Workflow to Pull Teammates' Code Safely

To pull your teammates' changes without losing your local work or messing up your branch, choose **Option 1 (Branching)** or **Option 2 (Stash & Backup)**:

---

### Option 1: Commit to a Dedicated Feature Branch (Best Practice)

This is the safest and cleanest Git workflow:

```bash
# 1. Create and switch to a new branch for your admin work
git checkout -b feat/admin-dashboard-and-fixes

# 2. Add and commit all your current changes
git add .
git commit -m "feat: complete admin dashboard, endpoints, and chat pipeline fixes"

# 3. Switch to main (or development) and pull the latest changes from your team
git checkout main
git pull origin main

# 4. Merge or rebase your admin feature branch onto the updated main branch
git checkout feat/admin-dashboard-and-fixes
git rebase main

# If there are any minor conflicts in shared files (like main.py or App.tsx), resolve them, then:
# git add <resolved-files>
# git rebase --continue
```

---

### Option 2: Git Stash + Patch File Backup (Quick & Safe)

If you prefer to stay on your current branch:

```bash
# 1. Create a hard backup patch file of all current uncommitted changes
git diff > my_admin_changes.patch
# For untracked files, create a zip or archive
git status --short

# 2. Stash your changes (including untracked files)
git stash -u -m "admin-dashboard-work"

# 3. Pull latest changes from your teammates
git pull origin <branch-name>

# 4. Re-apply your stashed work
git stash pop
```

If `git stash pop` flags any conflict on a shared file (e.g. `main.py`), you can open that file, accept both additions (your admin router + your teammates' new routes), and everything will continue running smoothly.
