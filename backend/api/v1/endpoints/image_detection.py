"""
Image detection endpoints for AI-generated content detection.
"""

import os
import tempfile
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, validator

from core.config import settings
from schemas.image_detection import ImageDetectionResponse
from services.image_detection_service import ImageDetectionService
from utils.logging import get_logger


class URLImageDetectionRequest(BaseModel):
    """Request for detecting image from URL."""

    image_url: str = Field(..., description="URL of the image to analyze")
    model_name: Optional[str] = Field("auto", description="Model to use for detection (default: auto, options: auto, ssp, clipbased)")
    threshold: Optional[float] = Field(None, description="Detection threshold")

    @validator("image_url")
    def validate_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class ImageModelsResponse(BaseModel):
    """Response listing available image detection models only."""

    image_models: List[str] = Field(..., description="Available image detection models")
    default_image_model: str = Field(..., description="Default image detection model")


logger = get_logger(__name__)
router = APIRouter()

# Supported image formats
SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
SUPPORTED_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/bmp", "image/tiff", "image/webp"}


def _validate_image_file(file: UploadFile) -> None:
    """Validate uploaded image file."""
    # Check file extension
    if not any(file.filename.lower().endswith(ext) for ext in SUPPORTED_IMAGE_FORMATS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format. Supported formats: {', '.join(SUPPORTED_IMAGE_FORMATS)}",
        )

    # Check MIME type
    if file.content_type and file.content_type.lower() not in SUPPORTED_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported MIME type: {file.content_type}")


@router.get("/image/models", response_model=ImageModelsResponse)
async def get_available_models():
    """
    Get list of available image detection models.
    """

    try:
        service = ImageDetectionService()
        image_models = service.get_available_models()

        return ImageModelsResponse(
            image_models=image_models,
            default_image_model="auto",
        )

    except Exception as e:
        logger.error("Failed to get available models", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get available models")


@router.post("/image/detect", response_model=ImageDetectionResponse)
async def detect_image_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Image file to analyze"),
    model_name: Optional[str] = Form(
        default="auto", description="Model to use for detection (default: auto, options: auto, ssp, clipbased)"
    ),
    threshold: Optional[float] = Form(default=0.0, description="Detection threshold (default: 0.0, model-specific)"),
):
    """
    Upload and analyze an image file for AI generation detection.

    - **file**: Image file (JPEG, PNG, BMP, TIFF, WebP)
    - **model_name**: Model to use for detection (default: auto, options: auto, ssp, clipbased)
    - **threshold**: Detection threshold (default: 0.0, model-specific)
    """

    # Validate file
    _validate_image_file(file)

    # Check file size
    contents = await file.read()
    if len(contents) > settings.max_file_size:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File too large. Maximum size: {settings.max_file_size} bytes")

    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp_file:
            tmp_file.write(contents)
            tmp_file_path = tmp_file.name

        try:
            # Create service and process image
            effective_model_name = model_name if model_name is not None else "auto"
            service = ImageDetectionService(model_name=effective_model_name)

            response = service.process_image_file(tmp_file_path, threshold=threshold)

            # Clean up service if needed
            background_tasks.add_task(service.cleanup)

            return response

        finally:
            # Clean up temporary file
            background_tasks.add_task(os.unlink, tmp_file_path)

    except Exception as e:
        logger.error("Image detection failed", filename=file.filename, error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Image detection failed: {str(e)}")


@router.post("/image/detect-url", response_model=ImageDetectionResponse)
async def detect_image_from_url(request: URLImageDetectionRequest, background_tasks: BackgroundTasks):
    """
    Analyze an image from URL for AI generation detection.

    - **image_url**: URL of the image to analyze
    - **model_name**: Model to use for detection (default: auto, options: auto, ssp, clipbased)
    - **threshold**: Detection threshold (default: 0.0, model-specific)
    """

    try:
        # Create service and process image from URL
        effective_model_name = request.model_name if request.model_name is not None else "auto"
        service = ImageDetectionService(model_name=effective_model_name)

        response = service.process_image_from_url(request.image_url, threshold=request.threshold)

        # Clean up service if needed
        background_tasks.add_task(service.cleanup)

        return response

    except Exception as e:
        logger.error("URL image detection failed", image_url=request.image_url, error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"URL image detection failed: {str(e)}")
