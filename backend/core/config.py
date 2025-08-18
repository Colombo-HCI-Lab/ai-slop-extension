"""
Configuration management for the FastAPI application.
"""

from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    # API settings
    api_title: str = "AI Content Detection API"
    api_description: str = """
    FastAPI service for AI-generated content detection using SlowFast models for videos and ClipBased models for images.
    
    This API provides endpoints to analyze videos and images to detect whether they contain AI-generated content.
    It uses Facebook's SlowFast models for video temporal feature extraction and ClipBased detection for image analysis.
    
    ## Features
    - Upload and analyze video files for AI-generated content detection
    - Upload and analyze image files for AI-generated content detection
    - Support for multiple video formats (MP4, AVI, MOV, WebM)
    - Support for multiple image formats (JPEG, PNG, BMP, TIFF, WebP)
    - Batch image processing
    - Model comparison capabilities
    - URL-based detection for images
    - Real-time health monitoring
    - Model information and statistics
    
    ## Video Models
    - SlowFast R50: Fast inference with good accuracy
    - SlowFast R101: Higher accuracy with slower inference
    - X3D-M: Efficient 3D CNN model
    
    ## Image Models
    - ClipBased: State-of-the-art CLIP-based detection (default)
    """
    api_version: str = "0.1.0"
    api_prefix: str = "/api/v1"

    # Server settings
    host: str = "0.0.0.0"
    port: int = 4000
    debug: bool = True  # Enable debug mode to show Swagger docs by default

    # File upload settings
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    max_file_size_async: int = 1024 * 1024 * 1024  # 1GB for async processing
    allowed_video_types: List[str] = ["video/mp4", "video/avi", "video/mov", "video/webm", "video/quicktime", "video/x-msvideo"]
    allowed_extensions: List[str] = [".mp4", ".avi", ".mov", ".webm"]

    # Image upload settings
    max_image_size: int = 10 * 1024 * 1024  # 10MB for images
    max_batch_size: int = 10  # Maximum images in batch request
    allowed_image_types: List[str] = ["image/jpeg", "image/jpg", "image/png", "image/bmp", "image/tiff", "image/webp"]
    allowed_image_extensions: List[str] = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]

    # Directory settings
    upload_dir: Path = Field(default_factory=lambda: Path("tmp"))

    # Video Model settings
    default_model: str = "slowfast_r50"
    available_models: List[str] = ["slowfast_r50", "slowfast_r101", "x3d_m"]
    model_cache_size: int = 2  # Number of models to keep in memory
    device: Optional[str] = None  # Auto-detect if None

    # Image Model settings
    default_image_model: str = "clipbased"  # clipbased
    available_image_models: List[str] = ["clipbased"]
    image_detection_device: Optional[str] = None  # Auto-detect if None

    # Video processing settings
    default_num_frames: int = 32
    default_crop_size: int = 224
    default_side_size: int = 256
    default_sampling_rate: int = 2
    default_alpha: int = 4  # SlowFast alpha parameter

    # Detection settings
    confidence_threshold: float = 0.5
    top_k_predictions: int = 5

    # Logging settings
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Database settings
    database_url: str = "postgresql://postgres:cats@localhost:5432/ai_slop_extension"
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Google Gemini settings
    gemini_api_key: str = ""

    # JWT settings
    jwt_secret: str = "your-super-secret-jwt-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_days: int = 7

    # Cache settings
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl: int = 3600  # 1 hour in seconds
    enable_cache: bool = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Ensure directories exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        # Auto-detect device if not specified or set to "auto"
        if self.device is None or self.device.lower() == "auto":
            import torch

            self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Auto-detect image detection device
        if self.image_detection_device is None or self.image_detection_device.lower() == "auto":
            import torch

            self.image_detection_device = "cuda" if torch.cuda.is_available() else "cpu"


# Global settings instance
settings = Settings()
