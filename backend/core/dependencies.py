"""
FastAPI dependencies for the application.
"""

import logging
from typing import Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

from core.config import settings
from services.video_detection_service import DetectionService

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
_detection_services: Dict[str, DetectionService] = {}


def get_detection_service(model_name: Optional[str] = None, current_user=Depends(get_current_user)) -> DetectionService:
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

    # Check cache
    if model_name not in _detection_services:
        # Implement LRU cache logic if needed
        if len(_detection_services) >= settings.model_cache_size:
            # Remove oldest service (simple FIFO for now)
            oldest_key = next(iter(_detection_services))
            del _detection_services[oldest_key]
            logging.info(f"Removed cached model: {oldest_key}")

        # Create new service
        try:
            _detection_services[model_name] = DetectionService(model_name=model_name, device=settings.device)
            logging.info(f"Loaded model: {model_name}")
        except Exception as e:
            logging.error(f"Failed to load model {model_name}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to load model: {model_name}")

    return _detection_services[model_name]


def get_logger() -> logging.Logger:
    """Get configured logger instance."""
    return logging.getLogger(__name__)
