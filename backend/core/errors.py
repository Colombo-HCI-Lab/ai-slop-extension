"""
Exception handlers and error response normalization.
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.config import settings
from schemas.responses import ErrorResponse, ValidationErrorResponse
from utils.logging import get_logger


def register_exception_handlers(app: FastAPI) -> None:
    """Attach standard exception handlers to the app."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error="http_error", message=exc.detail, status_code=exc.status_code
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ValidationErrorResponse(
                errors=[{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger = get_logger("errors", component="exception_handler")
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

