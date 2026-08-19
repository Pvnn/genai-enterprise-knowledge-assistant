"""Tests for auth module.

Owner: P6
Import shared fixtures from conftest.py (owned by P2). Do NOT define
new fixture setups that duplicate what conftest.py already provides.

Coverage:
  - create_access_token()  : happy path, payload correctness
  - resolve_tenant()       : known, unknown, case-insensitive
  - POST /auth/login       : success, wrong password, bad tenant, wrong email
  - GET  /auth/me          : no token, garbage token, expired, valid
"""

from datetime import datetime, timezone
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

import app.models  # noqa: F401 — registers Document ORM so Enterprise mapper resolves
from app.auth.models import Enterprise, User
from app.auth.security import create_access_token
from app.auth.tenancy import resolve_tenant
from app.config import get_settings
from app.database import get_db
from app.main import app
from tests.conftest import TEST_TENANT_ID, TEST_USER_ID

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Test constants ─────────────────────────────────────────────────────────────
_TENANT_NAME = "Acme University"
_EMAIL = "admin@acme.com"
_PASSWORD = "secret123"


# ── Local async_client fixture (httpx 0.28+ requires ASGITransport) ────────────
# conftest.py uses AsyncClient(app=app) which was removed in httpx 0.28.
# This fixture is scoped to test_auth.py only; P2 should update conftest.py
# once all teams have migrated. See P3 PR for the team-wide action item.

@pytest_asyncio.fixture
async def auth_client(db_session: AsyncSession) -> AsyncClient:
    """Yield a test AsyncClient wired to the in-memory DB for auth tests."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _seed(session: AsyncSession) -> tuple[Enterprise, User]:
    """Insert a test Enterprise and User into the in-memory DB and flush.

    Flush (not commit) so rows are visible to the same session without
    being committed — the conftest fixture rolls back after each test.
    """
    enterprise = Enterprise(id=UUID(TEST_TENANT_ID), name=_TENANT_NAME)
    session.add(enterprise)
    await session.flush()

    user = User(
        id=UUID(TEST_USER_ID),
        tenant_id=enterprise.id,
        email=_EMAIL,
        password_hash=_pwd_context.hash(_PASSWORD),
        role="admin",
    )
    session.add(user)
    await session.flush()
    return enterprise, user


# ── create_access_token ────────────────────────────────────────────────────────

def test_create_access_token_returns_non_empty_string():
    """create_access_token returns a non-empty JWT string."""
    token = create_access_token(
        {"sub": TEST_USER_ID, "tenant_id": TEST_TENANT_ID, "email": _EMAIL, "role": "admin"}
    )
    assert isinstance(token, str)
    assert len(token) > 20


def test_create_access_token_payload_is_correct():
    """Decoded payload contains the expected sub, role, and exp claims."""
    settings = get_settings()
    token = create_access_token(
        {"sub": TEST_USER_ID, "tenant_id": TEST_TENANT_ID, "email": _EMAIL, "role": "admin"}
    )
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == TEST_USER_ID
    assert payload["role"] == "admin"
    assert "exp" in payload


# ── resolve_tenant ─────────────────────────────────────────────────────────────

async def test_resolve_tenant_unknown_raises_400(db_session: AsyncSession):
    """resolve_tenant raises HTTP 400 for an enterprise name not in the DB."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await resolve_tenant("totally_unknown_org_xyz", db_session)
    assert exc.value.status_code == 400


async def test_resolve_tenant_known_returns_uuid(db_session: AsyncSession):
    """resolve_tenant returns the enterprise UUID for a known name."""
    await _seed(db_session)
    result = await resolve_tenant(_TENANT_NAME, db_session)
    assert result == UUID(TEST_TENANT_ID)


async def test_resolve_tenant_is_case_insensitive(db_session: AsyncSession):
    """resolve_tenant matches the enterprise name case-insensitively."""
    await _seed(db_session)
    result = await resolve_tenant(_TENANT_NAME.lower(), db_session)
    assert result == UUID(TEST_TENANT_ID)


# ── POST /auth/login ───────────────────────────────────────────────────────────

async def test_login_success(auth_client: AsyncClient, db_session: AsyncSession):
    """Correct credentials return access_token, tenant_id, user_id, role."""
    await _seed(db_session)
    resp = await auth_client.post(
        "/auth/login",
        json={"email": _EMAIL, "password": _PASSWORD, "tenant_code": _TENANT_NAME},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["role"] == "admin"
    assert data["tenant_id"] == TEST_TENANT_ID
    assert data["user_id"] == TEST_USER_ID


async def test_login_wrong_password_returns_401(auth_client: AsyncClient, db_session: AsyncSession):
    """Wrong password → 401 Unauthorized."""
    await _seed(db_session)
    resp = await auth_client.post(
        "/auth/login",
        json={"email": _EMAIL, "password": "wrong_password", "tenant_code": _TENANT_NAME},
    )
    assert resp.status_code == 401


async def test_login_unknown_tenant_returns_400(auth_client: AsyncClient):
    """Unknown tenant_code → 400 Bad Request."""
    resp = await auth_client.post(
        "/auth/login",
        json={"email": _EMAIL, "password": _PASSWORD, "tenant_code": "FAKE_TENANT_999"},
    )
    assert resp.status_code == 400


async def test_login_wrong_email_returns_401(auth_client: AsyncClient, db_session: AsyncSession):
    """Correct tenant but non-existent email → 401 Unauthorized."""
    await _seed(db_session)
    resp = await auth_client.post(
        "/auth/login",
        json={"email": "nobody@nowhere.com", "password": _PASSWORD, "tenant_code": _TENANT_NAME},
    )
    assert resp.status_code == 401


# ── GET /auth/me ───────────────────────────────────────────────────────────────

async def test_me_no_token_returns_401(auth_client: AsyncClient):
    """No Authorization header → 401 (FastAPI rejects before get_current_user)."""
    resp = await auth_client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_garbage_token_returns_401(auth_client: AsyncClient):
    """Malformed Bearer token → 401 from get_current_user."""
    resp = await auth_client.get(
        "/auth/me", headers={"Authorization": "Bearer not.a.real.jwt"}
    )
    assert resp.status_code == 401


async def test_me_expired_token_returns_401(auth_client: AsyncClient):
    """JWT with a past expiry → 401 (python-jose raises JWTError on decode)."""
    settings = get_settings()
    expired_token = jwt.encode(
        {
            "sub": TEST_USER_ID,
            "tenant_id": TEST_TENANT_ID,
            "email": _EMAIL,
            "role": "admin",
            "exp": datetime(2000, 1, 1, tzinfo=timezone.utc),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    resp = await auth_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert resp.status_code == 401


async def test_me_valid_token_returns_identity(auth_client: AsyncClient, db_session: AsyncSession):
    """Valid token + existing DB user → 200 with correct identity fields."""
    await _seed(db_session)
    token = create_access_token(
        {"sub": TEST_USER_ID, "tenant_id": TEST_TENANT_ID, "email": _EMAIL, "role": "admin"}
    )
    resp = await auth_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == _EMAIL
    assert data["role"] == "admin"
    assert data["tenant_id"] == TEST_TENANT_ID
    assert data["user_id"] == TEST_USER_ID
