"""
Video detection schemas shared across services and endpoints.

This module contains schemas for video AI detection functionality including
video metadata, prediction results, and API request/response models.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, validator


class VideoInfo(BaseModel):
    """Video metadata information."""

    filename: str = Field(..., description="Original filename")
    duration: Optional[float] = Field(None, description="Video duration in seconds")
    fps: Optional[float] = Field(None, description="Frames per second")
    resolution: Optional[str] = Field(None, description="Video resolution (e.g., '1920x1080')")
    file_size: Optional[int] = Field(None, description="File size in bytes")


class Prediction(BaseModel):
    """Single prediction result from AI detection model."""

    class_name: str = Field(..., description="Predicted class name")
    probability: float = Field(..., ge=0.0, le=1.0, description="Prediction probability")
    class_index: int = Field(..., ge=0, description="Class index in the model")


class DetectionResult(BaseModel):
    """Video AI detection analysis result."""

    is_ai_generated: bool = Field(..., description="Whether the video is detected as AI-generated")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    model_used: str = Field(..., description="Name of the model used for detection")
    processing_time: float = Field(..., ge=0.0, description="Processing time in seconds")
    top_predictions: List[Prediction] = Field(..., description="Top K predictions from the model")

    @validator("top_predictions")
    def validate_predictions(cls, v):
        """Ensure at least one prediction is provided."""
        if not v:
            raise ValueError("At least one prediction must be provided")
        return v


class DetectionResponse(BaseModel):
    """Response from video detection API."""

    status: str = Field("completed", description="Processing status")
    video_info: VideoInfo = Field(..., description="Video metadata")
    detection_result: Optional[DetectionResult] = Field(None, description="Detection results")
    created_at: Optional[str] = Field(None, description="Processing timestamp")


class URLDetectionRequest(BaseModel):
    """Request for detecting video from URL."""

    video_url: str = Field(..., description="URL of the video to analyze")
    model_name: Optional[str] = Field("slowfast_r50", description="Model to use for detection (default: slowfast_r50)")
    threshold: Optional[float] = Field(0.5, ge=0.0, le=1.0, description="Detection threshold (0.0-1.0)")
    top_k: int = Field(5, ge=1, le=10, description="Number of top predictions to return")

    @validator("video_url")
    def validate_url(cls, v):
        """Validate that URL starts with http or https."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v
