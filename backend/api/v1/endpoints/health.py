"""
Health check endpoints.
"""

from typing import List

import psutil
import torch
from fastapi import APIRouter
from pydantic import BaseModel, Field

from core.config import settings


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    models_loaded: List[str] = Field(..., description="Currently loaded models")
    gpu_available: bool = Field(..., description="Whether GPU is available")
    disk_space_mb: float = Field(..., description="Available disk space in MB")


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns system health status including GPU availability and disk space.
    """

    # Get system info
    disk_usage = psutil.disk_usage("/")
    disk_space_mb = disk_usage.free / (1024 * 1024)

    # Check GPU availability
    gpu_available = torch.cuda.is_available()

    # Get loaded models (simplified - would need global model tracking)
    loaded_models = []  # TODO: Track loaded models globally

    return HealthResponse(
        status="healthy",
        version=settings.api_version,
        models_loaded=loaded_models,
        gpu_available=gpu_available,
        disk_space_mb=disk_space_mb,
    )
