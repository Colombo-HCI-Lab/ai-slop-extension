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
    port: int = Field(default=4000, env="PORT")  # Read from PORT env var, default to 4000 for local dev
    debug: bool = True  # Enable debug mode to show Swagger docs by default

    # File upload settings
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_video_types: List[str] = ["video/mp4", "video/avi", "video/mov", "video/webm", "video/quicktime", "video/x-msvideo"]
    allowed_extensions: List[str] = [".mp4", ".avi", ".mov", ".webm"]

    # Image upload settings
    max_image_size: int = 10 * 1024 * 1024  # 10MB for images
    max_batch_size: int = 10  # Maximum images in batch request

    # Directory for temporary media storage
    # Default to local relative path; deployment can override via TMP_DIR
    tmp_dir: Path = Field(default_factory=lambda: Path("tmp"))

    # Google Cloud Storage settings removed; storage is via local TMP_DIR backed by GCS Fuse

    # Video Model settings
    default_model: str = "x3d_m"
    available_models: List[str] = ["slowfast_r50", "slowfast_r101", "x3d_m"]
    model_cache_size: int = 2  # Number of models to keep in memory
    device: Optional[str] = None  # Auto-detect if None

    # Image Model settings
    default_image_model: str = "clipbased"

    # Detection settings
    confidence_threshold: float = 0.5
    top_k_predictions: int = 5

    # Concurrency and retry settings (services)
    text_max_concurrency: int = 2
    image_max_concurrency: int = 1
    video_max_concurrency: int = 1
    detection_timeout_seconds: float = 120.0
    detection_retry_max_attempts: int = 2
    detection_retry_backoff_base: float = 0.5

    # Split thread pools (avoid blocking light ops)
    detection_light_threads: int = 2
    image_heavy_threads: int = 2
    video_heavy_threads: int = 2

    # Logging settings
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Multi-modal fusion settings
    # Overall AI probability thresholds used for determining verdict
    # If average AI probability >= fusion_ai_threshold -> ai_slop
    # If average AI probability <= fusion_human_threshold -> human_content
    # Else -> uncertain
    fusion_ai_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    fusion_human_threshold: float = Field(default=0.4, ge=0.0, le=1.0)

    # Database settings - individual components
    db_name: str = "ai_slop_extension"
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_host: str = "localhost"
    db_port: int = 5432

    # Database connection settings
    database_echo: bool = False
    database_pool_size: int = 20
    database_max_overflow: int = 30
    database_pool_timeout: float = 30.0
    database_pool_recycle: int = 3600

    @property
    def database_url(self) -> str:
        """Construct database URL from individual components."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # Google Gemini settings
    gemini_api_key: str = ""
    gemini_max_concurrency: int = 1  # Per-worker limit; ~4 total with 4 workers
    gemini_timeout_seconds: float = 30.0  # Timeout per Gemini call
    gemini_retry_max_attempts: int = 3  # Retry attempts for Gemini operations
    gemini_retry_backoff_base: float = 0.5  # Exponential backoff base
    gemini_max_media_files: int = 10  # Cap media parts per prompt

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Ensure temporary directory exists
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

        # Auto-detect device if not specified or set to "auto"
        if self.device is None or self.device.lower() == "auto":
            import torch

            self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # No separate image_detection_device; using common device


# Global settings instance
settings = Settings()
