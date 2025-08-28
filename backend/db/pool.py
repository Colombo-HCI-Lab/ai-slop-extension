"""Database connection pool management."""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool
from sqlalchemy import text

from core.config import settings


class DatabasePool:
    """Singleton database connection pool manager."""

    _instance: Optional["DatabasePool"] = None
    _engine = None
    _session_factory = None
    _logger = logging.getLogger(__name__)

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DatabasePool, cls).__new__(cls)
        return cls._instance

    @classmethod
    async def setup(
        cls,
        pool_size: Optional[int] = None,
        max_overflow: Optional[int] = None,
        pool_timeout: Optional[float] = None,
        pool_recycle: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize the database connection pool."""
        if logger is not None:
            cls._logger = logger

        if cls._engine is not None:
            cls._logger.warning("Attempt to reinitialize database pool")
            return

        # Use settings defaults if not provided
        pool_size = pool_size or settings.database_pool_size
        max_overflow = max_overflow or settings.database_max_overflow
        pool_timeout = pool_timeout or settings.database_pool_timeout
        pool_recycle = pool_recycle or settings.database_pool_recycle

        try:
            # Create async engine with connection pooling
            cls._engine = create_async_engine(
                settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
                echo=settings.database_echo,
                poolclass=AsyncAdaptedQueuePool,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=pool_timeout,
                pool_pre_ping=True,  # Validate connections before use
                pool_recycle=pool_recycle,
            )

            # Create session factory
            cls._session_factory = async_sessionmaker(
                cls._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            cls._logger.info(
                f"Database pool created successfully - pool_size={pool_size}, max_overflow={max_overflow}, pool_timeout={pool_timeout}"
            )

        except Exception as e:
            cls._logger.error(f"Error during database pool setup: {e}")
            raise

    @classmethod
    async def get_session(cls) -> AsyncSession:
        """Get a database session from the pool."""
        if not cls._session_factory:
            cls._logger.error("Database pool has not been initialized")
            raise RuntimeError("Database pool has not been initialized. Call setup() first.")

        # Return new session from factory directly
        # pool_pre_ping=True in engine config handles connection validation
        return cls._session_factory()

    @classmethod
    async def get_session_context(cls):
        """Get a database session as an async context manager."""
        if not cls._session_factory:
            cls._logger.error("Database pool has not been initialized")
            raise RuntimeError("Database pool has not been initialized. Call setup() first.")

        session = cls._session_factory()

        class SessionContext:
            def __init__(self, session):
                self.session = session

            async def __aenter__(self):
                return self.session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if exc_type:
                    await self.session.rollback()
                else:
                    await self.session.commit()
                await self.session.close()

        return SessionContext(session)

    @classmethod
    async def close(cls):
        """Close the database connection pool."""
        if not cls._engine:
            cls._logger.warning("Database pool was not initialized")
            return

        try:
            await cls._engine.dispose()
            cls._logger.info("Database pool closed successfully")
            cls._engine = None
            cls._session_factory = None

        except Exception as e:
            cls._logger.error(f"Error during database pool teardown: {e}")
            raise

    @classmethod
    async def __aenter__(cls):
        """Async context manager entry."""
        await cls.setup()
        return cls

    @classmethod
    async def __aexit__(cls, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await cls.close()

    @classmethod
    def get_engine(cls):
        """Get the SQLAlchemy engine for migrations and direct access."""
        if not cls._engine:
            raise RuntimeError("Database pool has not been initialized. Call setup() first.")
        return cls._engine


# Global database pool instance
database_pool = DatabasePool()
