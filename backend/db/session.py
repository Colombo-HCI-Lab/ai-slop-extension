"""Database session management."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from db.pool import database_pool
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session from connection pool."""
    session = await database_pool.get_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# Legacy compatibility - keep engine accessible for migrations
def get_engine():
    """Get the SQLAlchemy engine for migrations and direct access."""
    return database_pool.get_engine()
