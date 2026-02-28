"""
SQLAlchemy Async Engine and Session Configuration.

Provides async database engine and session factory with proper pooling.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import TypeAlias

from sqlalchemy import Pool
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, QueuePool

from file_validator.config import AppSettings, get_settings

logger: logging.Logger = logging.getLogger(__name__)

type AsyncSessionLocal = async_sessionmaker[AsyncSession]
# Global engine instance
_engine: AsyncEngine | None = None
_session_factory: AsyncSessionLocal | None = None


async def get_async_engine() -> AsyncEngine:
    """
    Create or retrieve async SQLAlchemy engine.

    Automatically selects appropriate pool based on database type:
    - SQLite: NullPool (no connection pooling)
    - PostgreSQL: QueuePool (connection pooling)

    Returns:
        AsyncEngine: Configured async engine instance
    """
    global _engine

    if _engine is not None:
        return _engine

    settings: AppSettings = get_settings()
    db_url: str = settings.database.database_url

    # Convert sqlite:// to sqlite+aiosqlite://
    if db_url.startswith("sqlite://"):
        db_url = db_url.replace("sqlite://", "sqlite+aiosqlite:///")
        logger.info("Using SQLite database: %s", db_url)
        pool_class = NullPool
    else:
        logger.info("Using PostgreSQL database")
        pool_class = QueuePool

    _engine: AsyncEngine = create_async_engine(
        db_url,
        echo=settings.database.echo,
        pool_pre_ping=True,
        poolclass=pool_class,
        pool_size=settings.database.pool_size if pool_class == QueuePool else None,
        max_overflow=settings.database.max_overflow if pool_class == QueuePool else None,
    )

    logger.info("Async database engine created successfully")
    return _engine


async def get_async_session_factory() -> AsyncSessionLocal:
    """
    Create async session factory.

    Returns:
        async_sessionmaker: Session factory for creating sessions
    """
    global _session_factory

    if _session_factory is not None:
        return _session_factory

    engine: AsyncEngine = await get_async_engine()
    _session_factory: AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    logger.info("Async session factory created")
    return _session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency: Get async database session.

    Yields:
        AsyncSession: Database session for the request

    Usage in routers:
        @router.post("/endpoint")
        async def endpoint(session: AsyncSession = Depends(get_async_session)):
            ...
    """
    factory: AsyncSessionLocal = await get_async_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Initialize database - create all tables.

    Should be called during application startup.
    """
    from file_validator.database.models import Base

    engine: AsyncEngine = await get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized - all tables created")


async def dispose_db():
    """
    Cleanup database resources.

    Should be called during application shutdown.
    """
    global _engine, _session_factory

    if _engine:
        await _engine.dispose()
        logger.info("Database engine disposed")
        _engine = None
        _session_factory = None
