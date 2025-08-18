"""
Text detection schemas shared across services and endpoints.

This module contains schemas for text AI detection functionality including
request/response models for analyzing Facebook posts and other text content.
"""

from typing import Optional
from pydantic import BaseModel, Field


class DetectRequest(BaseModel):
    """Request for text content AI detection."""

    post_id: str = Field(..., description="Facebook post ID")
    content: str = Field(..., description="Text content to analyze")
    author: Optional[str] = Field(None, description="Post author")
    metadata: Optional[dict] = Field(None, description="Additional metadata")


class DetectResponse(BaseModel):
    """Response for text content AI detection."""

    post_id: str = Field(..., description="Facebook post ID")
    verdict: str = Field(..., description="Detection verdict: ai_slop, human_content, or uncertain")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    explanation: str = Field(..., description="Explanation for the verdict")
    timestamp: str = Field(..., description="Analysis timestamp")
    debug_info: Optional[dict] = Field(None, description="Debug information")
