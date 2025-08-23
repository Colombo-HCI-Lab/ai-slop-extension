"""
Content detection schemas for multi-modal AI detection.

This module contains schemas for multi-modal AI detection functionality including
request/response models for analyzing content that may contain text, images, and videos.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ContentDetectionRequest(BaseModel):
    """Request for multi-modal content AI detection."""

    post_id: str = Field(..., description="Content post ID")
    content: str = Field(..., description="Text content to analyze")
    author: Optional[str] = Field(None, description="Content author")
    metadata: Optional[dict] = Field(None, description="Additional metadata")
    image_urls: Optional[List[str]] = Field(default=[], description="Image URLs from the content")
    video_urls: Optional[List[str]] = Field(default=[], description="Video URLs from the content (deprecated - use post_url)")
    post_url: Optional[str] = Field(None, description="Facebook post URL for yt-dlp video extraction")
    has_videos: Optional[bool] = Field(False, description="Whether the post contains videos")


class ContentDetectionResponse(BaseModel):
    """Response for multi-modal content AI detection."""

    post_id: str = Field(..., description="Content post ID")
    verdict: str = Field(..., description="Detection verdict: ai_slop, human_content, or uncertain")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score (legacy)")
    explanation: str = Field(..., description="Explanation for the verdict")
    timestamp: str = Field(..., description="Analysis timestamp")

    # Separate AI probability and confidence for each modality
    text_ai_probability: Optional[float] = Field(None, ge=0.0, le=1.0, description="Text AI probability (0.0 = human, 1.0 = AI)")
    text_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Text analysis confidence")

    image_ai_probability: Optional[float] = Field(None, ge=0.0, le=1.0, description="Image AI probability (0.0 = human, 1.0 = AI)")
    image_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Image analysis confidence")

    video_ai_probability: Optional[float] = Field(None, ge=0.0, le=1.0, description="Video AI probability (0.0 = human, 1.0 = AI)")
    video_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Video analysis confidence")

    # Detailed analysis results for backward compatibility
    text_analysis: Optional[dict] = Field(None, description="Text analysis results")
    image_analysis: Optional[List[dict]] = Field(None, description="Image analysis results")
    video_analysis: Optional[List[dict]] = Field(None, description="Video analysis results")
    debug_info: Optional[dict] = Field(None, description="Debug information")
