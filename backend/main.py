"""
FastAPI main application.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.v1.router import api_router
from core.config import settings
from schemas.responses import ErrorResponse, ValidationErrorResponse
from utils.logging import setup_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    setup_logging()
    logger = get_logger("main", component="application")
    logger.info(
        "Starting AI Detection API",
        available_models=settings.available_models,
        default_model=settings.default_model,
        device=settings.device,
        debug_mode=settings.debug,
    )

    # Create upload directories
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Upload directory initialized", path=str(settings.upload_dir))

    yield

    # Shutdown
    logger.info("Shutting down AI Detection API")


# Create FastAPI app
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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code, content=ErrorResponse(error="http_error", message=exc.detail, status_code=exc.status_code).dict()
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ValidationErrorResponse(
            errors=[{"loc": error["loc"], "msg": error["msg"], "type": error["type"]} for error in exc.errors()]
        ).dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger = get_logger("main", component="exception_handler")
    logger.error(
        "Unhandled exception occurred",
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
        ).dict(),
    )


# Root endpoint
@app.get("/", tags=["default"])
async def root():
    """Root endpoint."""
    return {
        "message": "SlowFast Video Detection API",
        "version": settings.api_version,
        "docs": "/docs" if settings.debug else "Documentation disabled in production",
        "health": f"{settings.api_prefix}/health",
    }


# Include API router
app.include_router(api_router, prefix=settings.api_prefix)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.debug, log_level=settings.log_level.lower())
