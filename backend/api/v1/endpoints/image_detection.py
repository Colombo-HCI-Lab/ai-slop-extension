"""
Image detection endpoints for AI-generated content detection.
"""

import os
import tempfile
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status, Depends
from pydantic import BaseModel, Field

from core.config import settings
from schemas.image_detection import ImageDetectionResponse
from services.detections.interfaces import ImageDetectionServiceProtocol
from core.dependencies import get_image_detection_service
from utils.logging import get_logger


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
async def get_available_models(service: ImageDetectionServiceProtocol = Depends(get_image_detection_service)):
    """
    Get list of available image detection models.
    """

    try:
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
    threshold: Optional[float] = Form(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Detection threshold (0.0-1.0; model-specific)",
    ),
    service: ImageDetectionServiceProtocol = Depends(get_image_detection_service),
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
    if len(contents) > settings.max_image_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {settings.max_image_size} bytes",
        )

    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp_file:
            tmp_file.write(contents)
            tmp_file_path = tmp_file.name

        try:
            # Process image using DI-provided service
            effective_model_name = model_name if model_name is not None else "auto"
            if effective_model_name and effective_model_name != service.model_name:
                service.model_name = effective_model_name
            response = await service.process_image_file_async(tmp_file_path, threshold=threshold)

            return response

        finally:
            # Clean up temporary file
            background_tasks.add_task(os.unlink, tmp_file_path)

    except Exception as e:
        logger.error("Image detection failed", filename=file.filename, error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Image detection failed: {str(e)}")
