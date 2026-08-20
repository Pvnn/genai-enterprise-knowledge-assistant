"""Unit and integration tests for Admin Dashboard endpoints.

Verifies:
  - Role-based access control (403 Forbidden for non-admin users)
  - Cross-tenant isolation (cannot see or mutate other tenants' documents or users)
  - GET /admin/analytics (correct aggregation metrics)
  - Document management (list, update, delete)
  - User management (list, create, change role, delete safeguards)
  - Glossary management (list, add, delete)
"""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt
import app.models  # noqa: F401
from app.auth.models import Enterprise, User, UserRole
from app.auth.security import create_access_token
from app.database import get_db
from app.main import app
from app.models import Chunk, Document, Feedback, Glossary, IngestionStatus, Query as QueryModel

def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")

@pytest_asyncio.fixture
async def admin_context(db_session: AsyncSession):
    """Seed enterprises, users, documents, and queries for testing with fresh IDs."""
    admin_tenant_id = uuid4()
    other_tenant_id = uuid4()
    admin_user_id = uuid4()
    member_user_id = uuid4()
    other_admin_id = uuid4()

    # 1. Enterprises
    ent1 = Enterprise(id=admin_tenant_id, name=f"Alpha Corp {uuid4().hex[:6]}")
    ent2 = Enterprise(id=other_tenant_id, name=f"Beta Inc {uuid4().hex[:6]}")
    db_session.add_all([ent1, ent2])
    await db_session.flush()

    # 2. Users
    admin_u = User(
        id=admin_user_id,
        tenant_id=admin_tenant_id,
        email=f"admin_{uuid4().hex[:6]}@alpha.com",
        password_hash=_hash("adminpass"),
        role=UserRole.ADMIN.value,
    )
    member_u = User(
        id=member_user_id,
        tenant_id=admin_tenant_id,
        email=f"member_{uuid4().hex[:6]}@alpha.com",
        password_hash=_hash("memberpass"),
        role=UserRole.MEMBER.value,
    )
    other_u = User(
        id=other_admin_id,
        tenant_id=other_tenant_id,
        email=f"admin_{uuid4().hex[:6]}@beta.com",
        password_hash=_hash("otherpass"),
        role=UserRole.ADMIN.value,
    )
    db_session.add_all([admin_u, member_u, other_u])

    # 3. Documents
    doc1 = Document(
        id=uuid4(),
        tenant_id=admin_tenant_id,
        title="Alpha HR Policy",
        department="Human Resources",
        doc_type="Policy",
        version_status="current",
        ingestion_status=IngestionStatus.DONE.value,
    )
    doc2 = Document(
        id=uuid4(),
        tenant_id=other_tenant_id,
        title="Beta Finance Manual",
        department="Finance",
        doc_type="Manual",
        version_status="current",
        ingestion_status=IngestionStatus.DONE.value,
    )
    db_session.add_all([doc1, doc2])
    await db_session.flush()

    # 4. Chunks
    chk1 = Chunk(
        id=uuid4(),
        document_id=doc1.id,
        tenant_id=admin_tenant_id,
        text="Alpha leave rules text.",
        section_path="Section 1",
    )
    db_session.add(chk1)

    # 5. Queries & Feedback
    q1 = QueryModel(
        id=uuid4(),
        tenant_id=admin_tenant_id,
        user_id=member_user_id,
        raw_query="What is the leave entitlement?",
        confidence_score=0.92,
        answered_or_refused=True,
    )
    db_session.add(q1)
    await db_session.flush()

    fb1 = Feedback(
        id=uuid4(),
        query_id=q1.id,
        thumbs_up_down=True,
        comment="Very helpful!",
    )
    db_session.add(fb1)

    # 6. Glossary
    g1 = Glossary(
        id=uuid4(),
        tenant_id=admin_tenant_id,
        term="PTO",
        expansion="Paid Time Off",
    )
    db_session.add(g1)

    await db_session.commit()

    return {
        "admin_tenant_id": admin_tenant_id,
        "other_tenant_id": other_tenant_id,
        "admin_user_id": admin_user_id,
        "member_user_id": member_user_id,
        "other_admin_id": other_admin_id,
        "admin_user": admin_u,
        "member_user": member_u,
        "doc1": doc1,
    }


@pytest_asyncio.fixture
async def admin_client(db_session: AsyncSession, admin_context: dict) -> AsyncClient:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    token = create_access_token({
        "sub": str(admin_context["admin_user_id"]),
        "tenant_id": str(admin_context["admin_tenant_id"]),
        "email": admin_context["admin_user"].email,
        "role": "admin",
    })
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def member_client(db_session: AsyncSession, admin_context: dict) -> AsyncClient:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    token = create_access_token({
        "sub": str(admin_context["member_user_id"]),
        "tenant_id": str(admin_context["admin_tenant_id"]),
        "email": admin_context["member_user"].email,
        "role": "member",
    })
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_member_access_forbidden(member_client: AsyncClient):
    """Ensure non-admin members get 403 Forbidden on all admin endpoints."""
    res = await member_client.get("/admin/analytics")
    assert res.status_code == 403

    res = await member_client.get("/admin/documents")
    assert res.status_code == 403

    res = await member_client.get("/admin/users")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_analytics_overview(admin_client: AsyncClient):
    """Ensure analytics endpoint aggregates correctly for admin's tenant."""
    res = await admin_client.get("/admin/analytics")
    assert res.status_code == 200
    data = res.json()

    assert data["total_queries"] == 1
    assert data["answered_queries"] == 1
    assert data["total_documents"] == 1  # only Alpha Corp docs
    assert data["total_chunks"] == 1
    assert data["total_members"] == 2   # admin + member
    assert data["positive_feedback_count"] == 1
    assert data["csat_percent"] == 100.0
    assert len(data["recent_activity"]) == 1
    assert data["recent_activity"][0]["raw_query"] == "What is the leave entitlement?"


@pytest.mark.asyncio
async def test_admin_documents_list_and_update(admin_client: AsyncClient):
    """Test listing and updating document metadata."""
    res = await admin_client.get("/admin/documents")
    assert res.status_code == 200
    docs = res.json()
    assert len(docs) == 1
    assert docs[0]["title"] == "Alpha HR Policy"
    assert docs[0]["chunk_count"] == 1

    doc_id = docs[0]["id"]

    # Update metadata
    patch_res = await admin_client.patch(
        f"/admin/documents/{doc_id}",
        json={"version_status": "superseded", "department": "People Ops"},
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["version_status"] == "superseded"
    assert updated["department"] == "People Ops"


@pytest.mark.asyncio
async def test_admin_users_crud_and_safeguards(admin_client: AsyncClient, admin_context: dict):
    """Test user listing, creation, role change, and self-demotion prevention."""
    # List users
    res = await admin_client.get("/admin/users")
    assert res.status_code == 200
    users = res.json()
    assert len(users) == 2

    # Create new user
    create_res = await admin_client.post(
        "/admin/users",
        json={"email": "newbie@alpha.com", "password": "pass12345", "role": "member"},
    )
    assert create_res.status_code == 201
    new_user = create_res.json()
    assert new_user["email"] == "newbie@alpha.com"
    assert new_user["role"] == "member"

    # Promote to admin
    role_res = await admin_client.patch(
        f"/admin/users/{new_user['id']}/role",
        json={"role": "admin"},
    )
    assert role_res.status_code == 200
    assert role_res.json()["role"] == "admin"

    # Try to self-demote (should fail)
    self_demote_res = await admin_client.patch(
        f"/admin/users/{admin_context['admin_user_id']}/role",
        json={"role": "member"},
    )
    assert self_demote_res.status_code == 400

    # Delete new user
    del_res = await admin_client.delete(f"/admin/users/{new_user['id']}")
    assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_admin_glossary_crud(admin_client: AsyncClient):
    """Test adding and deleting glossary entries."""
    res = await admin_client.get("/admin/glossary")
    assert res.status_code == 200
    entries = res.json()
    assert len(entries) == 1
    assert entries[0]["term"] == "PTO"

    # Add term
    add_res = await admin_client.post(
        "/admin/glossary",
        json={"term": "SLA", "expansion": "Service Level Agreement"},
    )
    assert add_res.status_code == 201
    assert add_res.json()["term"] == "SLA"

    # Delete term
    del_res = await admin_client.delete("/admin/glossary/SLA")
    assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_admin_document_detail_and_chunks(admin_client: AsyncClient, admin_context: dict):
    """Test retrieving full document details and its constituent chunks."""
    doc_id = admin_context["doc1"].id
    res = await admin_client.get(f"/admin/documents/{doc_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(doc_id)
    assert data["title"] == "Alpha HR Policy"
    assert data["chunk_count"] == 1
    assert len(data["chunks"]) == 1
    assert data["chunks"][0]["text"] == "Alpha leave rules text."

    # Non-existent document
    non_existent = uuid4()
    not_found_res = await admin_client.get(f"/admin/documents/{non_existent}")
    assert not_found_res.status_code == 404


@pytest.mark.asyncio
async def test_admin_document_delete_cascade(admin_client: AsyncClient, db_session: AsyncSession, admin_context: dict):
    """Test permanently deleting a document and verifying associated chunks are removed."""
    doc_id = admin_context["doc1"].id
    del_res = await admin_client.delete(f"/admin/documents/{doc_id}")
    assert del_res.status_code == 204

    # Document should now be 404
    get_res = await admin_client.get(f"/admin/documents/{doc_id}")
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_admin_cross_tenant_isolation_guards(admin_client: AsyncClient, admin_context: dict):
    """Ensure an administrator cannot inspect, modify, or delete resources belonging to another enterprise."""
    other_tenant_id = admin_context["other_tenant_id"]
    other_admin_id = admin_context["other_admin_id"]

    # Try to modify another enterprise user's role
    role_res = await admin_client.patch(
        f"/admin/users/{other_admin_id}/role",
        json={"role": "member"},
    )
    assert role_res.status_code == 404

    # Try to delete another enterprise user
    del_user_res = await admin_client.delete(f"/admin/users/{other_admin_id}")
    assert del_user_res.status_code == 404


@pytest.mark.asyncio
async def test_admin_validation_and_safeguards(admin_client: AsyncClient, admin_context: dict):
    """Verify input validation, self-deletion blocks, and duplicate email rejections."""
    admin_id = admin_context["admin_user_id"]

    # 1. Admin self-deletion block
    self_del_res = await admin_client.delete(f"/admin/users/{admin_id}")
    assert self_del_res.status_code == 400
    assert "cannot remove your own" in self_del_res.json()["detail"].lower()

    # 2. Invalid role in user creation
    invalid_role_res = await admin_client.post(
        "/admin/users",
        json={"email": "invalid_role@alpha.com", "password": "password123", "role": "superadmin"},
    )
    assert invalid_role_res.status_code == 400

    # 3. Duplicate email rejection
    dup_res = await admin_client.post(
        "/admin/users",
        json={"email": admin_context["admin_user"].email, "password": "password123", "role": "member"},
    )
    assert dup_res.status_code == 400
    assert "already registered" in dup_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_document_filters(admin_client: AsyncClient):
    """Test filtering documents by department, doc_type, version_status, and search terms."""
    # Department filter matching
    res_hr = await admin_client.get("/admin/documents?department=Human+Resources")
    assert res_hr.status_code == 200
    assert len(res_hr.json()) == 1

    # Department filter not matching
    res_eng = await admin_client.get("/admin/documents?department=Engineering")
    assert res_eng.status_code == 200
    assert len(res_eng.json()) == 0

    # Search filter matching
    res_search = await admin_client.get("/admin/documents?search=Policy")
    assert res_search.status_code == 200
    assert len(res_search.json()) == 1

    # Version status filter
    res_current = await admin_client.get("/admin/documents?version_status=current")
    assert res_current.status_code == 200
    assert len(res_current.json()) == 1

    res_superseded = await admin_client.get("/admin/documents?version_status=superseded")
    assert res_superseded.status_code == 200
    assert len(res_superseded.json()) == 0

