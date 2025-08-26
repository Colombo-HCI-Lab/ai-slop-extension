"""
Middleware configuration helpers.
"""

import time
from typing import Callable
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import Settings
from utils.logging import get_logger

logger = get_logger(__name__)


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Middleware to track request processing time."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        # Process request
        response = await call_next(request)

        # Calculate processing time
        process_time = time.perf_counter() - start_time
        process_time_ms = int(process_time * 1000)

        # Add timing header
        response.headers["X-Process-Time-Ms"] = str(process_time_ms)

        # Log slow requests
        if process_time_ms > 1000:  # Log requests slower than 1 second
            logger.warning(f"Slow request: {request.method} {request.url.path} took {process_time_ms}ms")
        elif process_time_ms > 500:  # Debug log for moderately slow requests
            logger.debug(f"Request: {request.method} {request.url.path} took {process_time_ms}ms")

        return response


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Basic rate limiting middleware for analytics endpoints."""

    def __init__(self, app, calls_per_minute: int = 60):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.request_times: dict = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only rate limit analytics endpoints
        if not request.url.path.startswith("/api/v1/analytics"):
            return await call_next(request)

        # Get client IP (consider X-Forwarded-For in production)
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Clean old entries
        if client_ip in self.request_times:
            self.request_times[client_ip] = [
                timestamp
                for timestamp in self.request_times[client_ip]
                if current_time - timestamp < 60  # Keep only last minute
            ]

        # Check rate limit
        if client_ip in self.request_times:
            if len(self.request_times[client_ip]) >= self.calls_per_minute:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return Response(content='{"error": "Rate limit exceeded"}', status_code=429, headers={"Content-Type": "application/json"})

        # Record request
        if client_ip not in self.request_times:
            self.request_times[client_ip] = []
        self.request_times[client_ip].append(current_time)

        return await call_next(request)


def configure_middleware(app: FastAPI, *, settings: Settings) -> None:
    """Configure CORS and other cross-cutting middleware."""
    # Add custom middleware
    app.add_middleware(RequestTimingMiddleware)
    app.add_middleware(RateLimitingMiddleware, calls_per_minute=120)  # 2 requests per second

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else ["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
