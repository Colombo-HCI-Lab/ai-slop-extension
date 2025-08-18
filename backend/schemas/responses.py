"""
Common API response schemas.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    detail: Optional[str] = Field(None, description="Additional error details")
    status_code: int = Field(..., description="HTTP status code")


class ValidationErrorResponse(BaseModel):
    """Validation error response format."""

    error: str = "validation_error"
    message: str = "Request validation failed"
    errors: list = Field(..., description="List of validation errors")
    status_code: int = 422
