"""
FastAPI dependencies for the application.
"""

import logging
from typing import Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

from core.config import settings
from services.detections.interfaces import (
    ImageDetectionServiceProtocol,
    VideoDetectionServiceProtocol,
)
from services.detections.registry import (
    get_image_detection_service as _resolve_image_service,
    get_video_detection_service as _resolve_video_service,
)

# Security
security = HTTPBearer(auto_error=False)


async def get_current_user(token: Optional[str] = Depends(security)):
    """
    Get current user from token (placeholder for authentication).
    Currently returns None to allow open access.
    """
    # TODO: Implement proper authentication if needed
    return None


# Service dependencies
_detection_services: Dict[str, VideoDetectionServiceProtocol] = {}


def get_detection_service(model_name: Optional[str] = None, current_user=Depends(get_current_user)) -> VideoDetectionServiceProtocol:
    """
    Get or create a detection service instance.
    Uses caching to avoid reloading models.
    """
    model_name = model_name or settings.default_model

    if model_name not in settings.available_models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model {model_name} not available. Available models: {settings.available_models}",
        )

    # Use singleton detection service to centralize resources/concurrency.
    try:
        return _resolve_video_service(model_name=model_name)
    except Exception as e:
        logging.error(f"Failed to initialize detection service: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to initialize detection service")


def get_image_detection_service(model_name: Optional[str] = None, current_user=Depends(get_current_user)) -> ImageDetectionServiceProtocol:
    """Dependency: image detection service via registry."""
    try:
        return _resolve_image_service(model_name=model_name)
    except Exception as e:
        logging.error(f"Failed to initialize image detection service: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to initialize image detection service")


def get_logger() -> logging.Logger:
    """Get configured logger instance."""
    return logging.getLogger(__name__)
