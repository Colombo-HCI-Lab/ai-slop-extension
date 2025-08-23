"""
Image detection schemas and models.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ImageInfo(BaseModel):
    """Image metadata information."""

    filename: str = Field(..., description="Original filename")
    size: Optional[str] = Field(None, description="Image dimensions (e.g., '1920x1080')")
    format: Optional[str] = Field(None, description="Image format (e.g., 'JPEG', 'PNG')")
    file_size: Optional[int] = Field(None, description="File size in bytes")


class ImageDetectionResult(BaseModel):
    """Image detection analysis result."""

    is_ai_generated: bool = Field(..., description="Whether the image is detected as AI-generated")
    confidence: float = Field(..., ge=0.0, description="Overall confidence score")
    model_used: str = Field(..., description="Name of the model used for detection")
    processing_time: float = Field(..., ge=0.0, description="Processing time in seconds")
    llr_score: Optional[float] = Field(None, description="Log-Likelihood Ratio score (ClipBased specific)")
    probability: Optional[float] = Field(None, ge=0.0, le=1.0, description="Raw probability score")
    threshold: Optional[float] = Field(None, description="Detection threshold used")
    metadata: Optional[dict] = Field(None, description="Additional model-specific metadata")


class ImageDetectionResponse(BaseModel):
    """Response from image detection API."""

    status: str = Field("completed", description="Processing status")
    image_info: ImageInfo = Field(..., description="Image metadata")
    detection_result: Optional[ImageDetectionResult] = Field(None, description="Detection results")
    created_at: Optional[str] = Field(None, description="Processing timestamp")
