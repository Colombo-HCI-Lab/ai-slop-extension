"""
Exception handlers and error response normalization.
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from pydantic import ValidationError

from core.config import settings
from schemas.responses import ErrorResponse, ValidationErrorResponse
from utils.logging import get_logger

logger = get_logger(__name__)


class MetricsValidationError(Exception):
    """Custom exception for metrics validation errors."""

    pass


class RateLimitExceeded(Exception):
    """Custom exception for rate limit exceeded."""

    pass


def register_exception_handlers(app: FastAPI) -> None:
    """Attach standard exception handlers to the app."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error="http_error", message=exc.detail, status_code=exc.status_code).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ValidationErrorResponse(
                errors=[{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
            ).model_dump(),
        )

    @app.exception_handler(OperationalError)
    async def database_error_handler(request: Request, exc: OperationalError):
        """Handle database connection errors."""
        logger.error(f"Database error: {exc}")

        # Check if it's a connection error
        if "connection" in str(exc).lower():
            return JSONResponse(
                status_code=503,
                content={"error": "Database temporarily unavailable", "message": "Please try again later", "retry_after": 30},
            )

        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="database_error", message="Database error occurred", detail=str(exc) if settings.debug else None, status_code=500
            ).model_dump(),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        """Handle data integrity violations."""
        logger.warning(f"Integrity error: {exc}")

        # Check for duplicate key violations
        if "duplicate key" in str(exc).lower():
            return JSONResponse(
                status_code=409,
                content=ErrorResponse(error="duplicate_entry", message="Duplicate entry detected", status_code=409).model_dump(),
            )

        # Check for foreign key violations
        if "foreign key" in str(exc).lower():
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(error="invalid_reference", message="Invalid reference to related data", status_code=400).model_dump(),
            )

        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error="data_integrity_violation",
                message="Data integrity violation",
                detail=str(exc) if settings.debug else None,
                status_code=400,
            ).model_dump(),
        )

    @app.exception_handler(MetricsValidationError)
    async def metrics_validation_error_handler(request: Request, exc: MetricsValidationError):
        """Handle metrics validation errors."""
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="metrics_validation_error", message="Invalid metrics data", detail=str(exc), status_code=422
            ).model_dump(),
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_error_handler(request: Request, exc: RateLimitExceeded):
        """Handle rate limit errors."""
        return JSONResponse(
            status_code=429,
            content=ErrorResponse(error="rate_limit_exceeded", message="Too many requests", detail=str(exc), status_code=429).model_dump(),
            headers={"Retry-After": "60"},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled exception",
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            request_url=str(request.url),
            request_method=request.method,
            exc_info=True,
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="internal_server_error",
                message="An internal server error occurred",
                detail=str(exc) if settings.debug else None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ).model_dump(),
        )
