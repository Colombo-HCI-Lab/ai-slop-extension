"""
Application factory for the FastAPI backend.

This module centralizes app creation so tests and scripts can
instantiate an application with custom settings when needed.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.v1.router import api_router
from core.config import Settings, settings as default_settings
from core.errors import register_exception_handlers
from core.middleware import configure_middleware
from utils.logging import setup_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan to initialize and tear down shared resources."""
    setup_logging()
    logger = get_logger("app", component="application")

    # Initialize database pool with retry and timeout
    from db.pool import database_pool
    import asyncio

    try:
        # Try to connect to database with timeout
        await asyncio.wait_for(
            database_pool.setup(logger=logger),
            timeout=10.0,  # 10 second timeout for database connection
        )
        logger.info("Database connection established successfully")
    except asyncio.TimeoutError:
        logger.warning("Database connection timed out during startup - continuing without database")
    except Exception as e:
        logger.warning(f"Database connection failed during startup: {e} - continuing without database")

    # Ensure temporary directory exists
    from core.config import settings

    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "App starting",
        available_models=settings.available_models,
        default_model=settings.default_model,
        device=settings.device,
        debug_mode=settings.debug,
        database_pool_size=settings.database_pool_size,
        database_max_overflow=settings.database_max_overflow,
    )

    yield

    # Shutdown
    try:
        await database_pool.close()
    except Exception as e:
        logger.warning(f"Error closing database pool: {e}")
    logger.info("App shutdown complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = settings or default_settings

    app = FastAPI(
        title=settings.api_title,
        description=settings.api_description,
        version=settings.api_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_tags=[
            {"name": "default", "description": "General API information and root endpoints"},
            {"name": "health", "description": "Health check and system monitoring endpoints"},
            {"name": "image-detection", "description": "AI image detection endpoints for analyzing image content"},
            {"name": "video-detection", "description": "AI video detection endpoints for analyzing video content and model information"},
        ],
        contact={
            "name": "SlowFast Video Detection API",
            "url": "https://github.com/facebookresearch/SlowFast",
        },
        license_info={
            "name": "Apache 2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        },
    )

    # Middleware and exception handlers
    configure_middleware(app, settings=settings)
    register_exception_handlers(app)

    # Root endpoint
    @app.get("/", tags=["default"])
    async def root():
        return {
            "message": "SlowFast Video Detection API",
            "version": settings.api_version,
            "docs": "/docs" if settings.debug else "Documentation disabled in production",
            "health": f"{settings.api_prefix}/health",
        }

    # Include API router
    app.include_router(api_router, prefix=settings.api_prefix)

    return app
