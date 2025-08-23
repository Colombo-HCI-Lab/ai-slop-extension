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
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (legacy)")
    explanation: str = Field(..., description="Explanation for the verdict")
    timestamp: str = Field(..., description="Analysis timestamp")

    # Separate AI probability and confidence for text
    text_ai_probability: Optional[float] = Field(None, ge=0.0, le=1.0, description="Text AI probability (0.0 = human, 1.0 = AI)")
    text_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Text analysis confidence")

    # Detailed analysis results for backward compatibility
    text_analysis: Optional[dict] = Field(None, description="Text analysis results")
    image_analysis: Optional[list] = Field(None, description="Image analysis results")
    video_analysis: Optional[list] = Field(None, description="Video analysis results")
    debug_info: Optional[dict] = Field(None, description="Debug information")
