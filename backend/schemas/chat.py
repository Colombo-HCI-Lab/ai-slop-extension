"""
Chat schemas shared across services and endpoints.

This module contains schemas for chat functionality including
chat messages, conversation requests, and AI-powered responses about posts.
"""

import uuid
from typing import Any, Dict, List, Union

from pydantic import Field, field_validator

from .base import UUIDBaseModel


class ChatRequest(UUIDBaseModel):
    """Request for sending a chat message about a post."""

    post_id: str = Field(..., description="Facebook post ID")
    message: str = Field(..., description="User message")
    user_id: Union[str, uuid.UUID] = Field(..., description="Unique user identifier (UUID)")

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v):
        """Validate and convert user_id to UUID."""
        if isinstance(v, uuid.UUID):
            return v
        try:
            return uuid.UUID(v)
        except ValueError:
            raise ValueError("user_id must be a valid UUID")
        return v


class Message(UUIDBaseModel):
    """Individual chat message in a conversation."""

    id: Union[str, uuid.UUID] = Field(..., description="Message ID")
    role: str = Field(..., description="Message role (user/assistant)")
    message: str = Field(..., description="Message content")
    created_at: str = Field(..., description="Message timestamp")


class ChatResponse(UUIDBaseModel):
    """Response for chat message with AI-generated content."""

    id: Union[str, uuid.UUID] = Field(..., description="Response message ID")
    message: str = Field(..., description="AI response message")
    suggested_questions: List[str] = Field(default_factory=list, description="Suggested follow-up questions")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context about the response")
    timestamp: str = Field(..., description="Response timestamp")
