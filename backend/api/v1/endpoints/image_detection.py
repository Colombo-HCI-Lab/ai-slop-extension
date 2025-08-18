"""
Image detection endpoints for AI-generated content detection.
"""

import logging
import time
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field, validator

from core.config import settings


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
    detection_result: ImageDetectionResult = Field(..., description="Detection results")
    created_at: Optional[str] = Field(None, description="Processing timestamp")


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


logger = logging.getLogger(__name__)
router = APIRouter()

# Global job storage (in production, use Redis or database)
_image_job_storage = {}

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


def _get_image_detector(model_name: str = "auto"):
    """Get the appropriate image detector based on model name."""
    try:
        if model_name == "auto" or model_name == "clipbased":
            # Try ClipBased first
            from clipbased_detection import ClipBasedImageDetector

            return ClipBasedImageDetector(), "clipbased"
        elif model_name == "ssp":
            # Try SSP detector
            try:
                from slowfast_detection.image_detection import SSPImageDetector

                return SSPImageDetector(), "ssp"
            except ImportError:
                logger.warning("SSP detector not available, falling back to ClipBased")
                from clipbased_detection import ClipBasedImageDetector

                return ClipBasedImageDetector(), "clipbased"
        else:
            raise ValueError(f"Unknown model: {model_name}")
    except ImportError as e:
        logger.error(f"Failed to import image detector: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Image detection models not available")


def _convert_detection_result(result: dict, model_name: str) -> ImageDetectionResult:
    """Convert detector result to API schema."""
    return ImageDetectionResult(
        is_ai_generated=result.get("is_ai_generated", False),
        confidence=result.get("confidence", 0.0),
        model_used=model_name,
        processing_time=result.get("processing_time", 0.0),
        llr_score=result.get("llr_score"),
        probability=result.get("probability"),
        threshold=result.get("threshold"),
        metadata=result.get("metadata", {}),
    )


def _create_image_info(file: UploadFile, file_size: int = None) -> ImageInfo:
    """Create ImageInfo from uploaded file."""
    return ImageInfo(
        filename=file.filename,
        size=None,  # Will be filled by detector if available
        format=file.content_type,
        file_size=file_size,
    )


@router.get("/image/models", response_model=ImageModelsResponse)
async def get_available_models():
    """
    Get list of available image detection models.
    """

    try:
        # Check which models are available
        image_models = []

        # Check ClipBased
        try:
            from clipbased_detection import ClipBasedImageDetector
            from clipbased_detection.config import config

            image_models.extend(config.get_available_models())
        except ImportError:
            logger.warning("ClipBased models not available")

        # Check SSP
        try:
            from slowfast_detection.image_detection import SSPImageDetector

            image_models.append("ssp")
        except ImportError:
            logger.warning("SSP model not available")

        # Add auto option
        if image_models:
            image_models.insert(0, "auto")

        return ImageModelsResponse(
            image_models=image_models,
            default_image_model="auto",
        )

    except Exception as e:
        logger.error(f"Failed to get available models: {e}")
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

    # Reset file pointer
    await file.seek(0)

    try:
        start_time = time.time()

        # Get detector
        effective_model_name = model_name if model_name is not None else "auto"
        detector, actual_model = _get_image_detector(effective_model_name)

        # Create temporary file
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp_file:
            tmp_file.write(contents)
            tmp_file_path = tmp_file.name

        try:
            # Run detection
            if hasattr(detector, "detect_image"):
                result = detector.detect_image(tmp_file_path, threshold=threshold)
            else:
                result = detector.detect(tmp_file_path)

            # Convert result
            detection_result = _convert_detection_result(result, actual_model)

            # Create image info
            image_info = _create_image_info(file, len(contents))
            if result.get("metadata", {}).get("image_size"):
                image_info.size = str(result["metadata"]["image_size"])

            response = ImageDetectionResponse(
                status="completed",
                image_info=image_info,
                detection_result=detection_result,
                created_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
            )

            # Clean up detector if needed
            if hasattr(detector, "cleanup"):
                background_tasks.add_task(detector.cleanup)

            return response

        finally:
            # Clean up temporary file
            background_tasks.add_task(os.unlink, tmp_file_path)

    except Exception as e:
        logger.error(f"Image detection failed: {e}")
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
        start_time = time.time()

        # Get detector
        effective_model_name = request.model_name if request.model_name is not None else "auto"
        detector, actual_model = _get_image_detector(effective_model_name)

        # Download and detect from URL
        if hasattr(detector, "detect_from_url"):
            result = detector.detect_from_url(request.image_url, threshold=request.threshold)
        else:
            # Fallback: download manually
            from clipbased_detection.utils import download_image_from_url

            image = download_image_from_url(request.image_url)

            # Save temporarily and detect
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                image.save(tmp_file, format="JPEG")
                tmp_file_path = tmp_file.name

            try:
                if hasattr(detector, "detect_image"):
                    result = detector.detect_image(tmp_file_path, threshold=request.threshold)
                else:
                    result = detector.detect(tmp_file_path)
            finally:
                background_tasks.add_task(os.unlink, tmp_file_path)

        # Convert result
        detection_result = _convert_detection_result(result, actual_model)

        # Create image info
        image_info = ImageInfo(
            filename=request.image_url.split("/")[-1] or "url_image",
            size=str(result.get("metadata", {}).get("image_size", "unknown")),
            format="unknown",
            file_size=None,
        )

        response = ImageDetectionResponse(
            status="completed",
            image_info=image_info,
            detection_result=detection_result,
            created_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
        )

        # Clean up detector if needed
        if hasattr(detector, "cleanup"):
            background_tasks.add_task(detector.cleanup)

        return response

    except Exception as e:
        logger.error(f"URL image detection failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"URL image detection failed: {str(e)}")
