"""
Middleware configuration helpers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import Settings


def configure_middleware(app: FastAPI, *, settings: Settings) -> None:
    """Configure CORS and other cross-cutting middleware."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else ["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

