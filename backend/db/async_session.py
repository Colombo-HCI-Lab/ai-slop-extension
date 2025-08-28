"""Async context manager for database operations."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from db.pool import database_pool
from utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session as an async context manager.

    This ensures proper transaction handling:
    - Commits on success
    - Rolls back on exception
    - Always closes the session

    Usage:
        async with get_async_session() as session:
            # perform database operations
            result = await session.execute(...)
    """
    session = await database_pool.get_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@asynccontextmanager
async def get_transactional_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session with explicit transaction management.

    This creates a nested transaction that can be rolled back independently.

    Usage:
        async with get_transactional_session() as session:
            # perform database operations in a transaction
            result = await session.execute(...)
    """
    session = await database_pool.get_session()
    try:
        async with session.begin():
            yield session
    finally:
        await session.close()
