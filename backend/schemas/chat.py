"""
Chat schemas shared across services and endpoints.

This module contains schemas for chat functionality including
chat messages, conversation requests, and AI-powered responses about posts.
"""

from typing import Any, Dict, List
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request for sending a chat message about a post."""

    post_id: str = Field(..., description="Facebook post ID")
    message: str = Field(..., description="User message")


class Message(BaseModel):
    """Individual chat message in a conversation."""

    id: str = Field(..., description="Message ID")
    role: str = Field(..., description="Message role (user/assistant)")
    message: str = Field(..., description="Message content")
    created_at: str = Field(..., description="Message timestamp")


class ChatResponse(BaseModel):
    """Response for chat message with AI-generated content."""

    id: str = Field(..., description="Response message ID")
    message: str = Field(..., description="AI response message")
    suggested_questions: List[str] = Field(default_factory=list, description="Suggested follow-up questions")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context about the response")
    timestamp: str = Field(..., description="Response timestamp")
