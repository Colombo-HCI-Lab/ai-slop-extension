"""
FastAPI application entrypoint; uses the app factory for instantiation.
"""

from app import create_app
from core.config import settings


# Keep the global `app` for tests and WSGI servers
app = create_app(settings)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
