"""
Video detection endpoints.
"""

from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status

from core.config import settings
from core.dependencies import get_detection_service
from schemas.video_detection import DetectionResponse, URLDetectionRequest
from services.detection_service import DetectionService
from services.video_processor import VideoProcessor
from utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Video processor instance
video_processor = VideoProcessor()


@router.get("/video/models")
async def get_available_models():
    """
    Get list of available AI detection models.

    Returns information about all available SlowFast models including their capabilities
    and supported formats.
    """

    models = []
    for model_name in settings.available_models:
        model_info = {
            "name": model_name,
            "description": f"SlowFast {model_name.upper()} model for video classification",
            "is_default": (model_name == settings.default_model),
            "supported_formats": settings.allowed_extensions,
        }
        models.append(model_info)

    return models


@router.post("/video/detect", response_model=DetectionResponse)
async def detect_video_upload(
    file: UploadFile = File(..., description="Video file to analyze"),
    model_name: Optional[str] = Form(
        default="slowfast_r50",
        description=f"Model to use for detection (default: slowfast_r50, options: {', '.join(settings.available_models)})",
    ),
    threshold: float = Form(0.5, description="Detection threshold (0.0-1.0)"),
    service: DetectionService = Depends(get_detection_service),
):
    """
    Upload and analyze a video file for AI generation detection.

    - **file**: Video file (MP4, AVI, MOV, WebM)
    - **model_name**: Model to use for detection (default: slowfast_r50, options: slowfast_r50, slowfast_r101, x3d_m)
    - **threshold**: Detection threshold for AI classification (0.0-1.0)
    """

    # Use default model if none specified
    if model_name is None:
        model_name = settings.default_model

    # Save uploaded file
    try:
        file_path = await video_processor.save_uploaded_file(file)
    except Exception as e:
        logger.error("File upload failed", filename=file.filename, error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Additional MIME type validation
    if not video_processor.validate_mime_type(file_path):
        video_processor.cleanup_file(file_path)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video file format")

    try:
        # Process video with specified model and threshold
        if model_name != service.model_name:
            # Create new service instance with the specified model
            model_service = DetectionService(model_name=model_name, device=service.device)
            model_service.set_threshold(threshold)
            result = model_service.process_video_file(file_path)
            # Clean up the temporary service
            model_service.cleanup()
        else:
            service.set_threshold(threshold)
            result = service.process_video_file(file_path)

        # Clean up file
        video_processor.cleanup_file(file_path)

        return result

    except Exception as e:
        # Clean up on error
        video_processor.cleanup_file(file_path)
        logger.error("Video processing failed (upload)", filename=file.filename, model_name=model_name, error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Video processing failed")


@router.post("/video/detect-url", response_model=DetectionResponse)
async def detect_video_from_url(
    request: URLDetectionRequest,
    service: DetectionService = Depends(get_detection_service),
):
    """
    Download and analyze a video from URL for AI generation detection.

    - **video_url**: Public URL of the video to analyze (HTTP/HTTPS only)
    - **model_name**: Model to use for detection (default: slowfast_r50, options: slowfast_r50, slowfast_r101, x3d_m)
    - **threshold**: Detection threshold for AI classification (0.0-1.0)
    """

    # Use default model if none specified
    if request.model_name is None:
        request.model_name = settings.default_model

    # Use threshold from request
    threshold = request.threshold if request.threshold is not None else 0.5

    # Download video from URL
    try:
        file_path = await video_processor.download_video_from_url(request.video_url)
    except HTTPException:
        raise  # Re-raise HTTP exceptions from download
    except Exception as e:
        logger.error("Video download failed", video_url=request.video_url, error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to download video from URL")

    try:
        # Process video with specified model and threshold
        if request.model_name != service.model_name:
            # Create new service instance with the specified model
            model_service = DetectionService(model_name=request.model_name, device=service.device)
            model_service.set_threshold(threshold)
            result = model_service.process_video_file(file_path)
            # Clean up the temporary service
            model_service.cleanup()
        else:
            service.set_threshold(threshold)
            result = service.process_video_file(file_path)

        # Clean up downloaded file
        video_processor.cleanup_file(file_path)

        return result

    except Exception as e:
        # Clean up on error
        video_processor.cleanup_file(file_path)
        logger.error(
            "Video processing failed (URL)", video_url=request.video_url, model_name=request.model_name, error=str(e), exc_info=True
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Video processing failed")
