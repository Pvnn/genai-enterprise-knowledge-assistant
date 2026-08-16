"""Shared pytest fixtures.

Owner: P2
All test modules must import fixtures from this file, NOT define their own
session/DB/user fixtures.  Doing so keeps fixture setup consistent across
all 8 independently-generated test files.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.database import Base, get_db

# ── In-memory SQLite for tests ────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    """Create all tables in the in-memory test database."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Yield a fresh AsyncSession for each test, rolled back on teardown."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncClient:
    """Yield a test AsyncClient with the DB dependency overridden."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()


# ── Shared test constants ─────────────────────────────────────────────────────
TEST_TENANT_ID = "11111111-1111-1111-1111-111111111111"
TEST_USER_ID   = "22222222-2222-2222-2222-222222222222"
TEST_DOC_ID    = "33333333-3333-3333-3333-333333333333"
