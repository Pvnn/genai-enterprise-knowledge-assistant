"""Async SQLAlchemy engine and session factory.

Owner: P2
Provides get_db() dependency for FastAPI route handlers.
All I/O must use async / await; no synchronous SQLAlchemy calls.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Neon's pooled endpoint runs PgBouncer in transaction-pooling mode, which
# conflicts with asyncpg's default prepared-statement caching. Use Neon's
# direct (unpooled) connection string, or pass statement_cache_size=0 in
# asyncpg connect_args if using the pooled endpoint.
engine = create_async_engine(
    settings.database_url,
    echo=(settings.app_env == "development"),
    pool_pre_ping=True,
    connect_args={"statement_cache_size": 0},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession per request.

    Yields:
        AsyncSession: An open async database session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
