"""
Detection service registry to resolve implementations via settings or parameters.
"""

from __future__ import annotations

from typing import Optional

from core.config import settings
from services.detections.interfaces import (
    ImageDetectionServiceProtocol,
    VideoDetectionServiceProtocol,
)
from services.image_detection_service import ImageDetectionService
from services.video_detection_service import DetectionService as _VideoService


def get_video_detection_service(model_name: Optional[str] = None) -> VideoDetectionServiceProtocol:
    """Resolve the video detection service (singleton) and set requested model if provided."""
    service = _VideoService.get_instance()
    # Align with requested or default model
    service.model_name = model_name or settings.default_model
    return service


def get_image_detection_service(model_name: Optional[str] = None) -> ImageDetectionServiceProtocol:
    """Resolve the image detection service (singleton) and set requested model if provided."""
    service = ImageDetectionService.get_instance()
    service.model_name = model_name or settings.default_image_model
    return service

