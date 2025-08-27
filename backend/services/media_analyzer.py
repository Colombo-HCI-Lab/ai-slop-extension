"""Unified media analyzer architecture for image and video detection."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from utils.logging import get_logger

logger = get_logger(__name__)


class MediaType(Enum):
    """Media type enumeration."""

    IMAGE = "image"
    VIDEO = "video"


@dataclass
class AnalysisResult:
    """Unified analysis result for media detection."""

    # Core detection results
    is_ai_generated: bool
    ai_probability: float  # 0.0 = human, 1.0 = AI
    confidence: float  # 0.0 to 1.0

    # Model information
    model_used: str
    processing_time: Optional[float] = None

    # Additional metadata
    llr_score: Optional[float] = None  # For ClipBased
    predictions: Optional[List[Dict]] = None  # For detailed predictions
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            "is_ai_generated": self.is_ai_generated,
            "ai_probability": self.ai_probability,
            "confidence": self.confidence,
            "model_used": self.model_used,
        }

        if self.processing_time is not None:
            result["processing_time"] = self.processing_time
        if self.llr_score is not None:
            result["llr_score"] = self.llr_score
        if self.predictions:
            result["predictions"] = self.predictions
        if self.metadata:
            result["metadata"] = self.metadata
        if self.error:
            result["error"] = self.error

        return result


@dataclass
class MediaFile:
    """Media file information for processing."""

    url: str
    local_path: Optional[Path] = None
    storage_path: Optional[str] = None
    storage_type: Optional[str] = None  # currently local-only
    media_type: MediaType = MediaType.IMAGE
    media_id: Optional[str] = None
    post_id: Optional[str] = None

    @property
    def has_local_file(self) -> bool:
        """Check if local file exists."""
        return self.local_path is not None and self.local_path.exists()


class MediaAnalyzer(ABC):
    """Abstract base class for media analyzers."""

    def __init__(self, device: str = "auto"):
        """
        Initialize media analyzer.

        Args:
            device: Device for inference ('auto', 'cuda', 'cpu')
        """
        self.device = device
        self._detector = None

    @abstractmethod
    async def analyze(self, media_file: MediaFile) -> AnalysisResult:
        """
        Analyze media file for AI generation.

        Args:
            media_file: Media file information

        Returns:
            Analysis result with detection scores
        """
        pass

    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """
        Get list of supported file formats.

        Returns:
            List of supported extensions (e.g., ['.jpg', '.png'])
        """
        pass

    @abstractmethod
    def get_mime_types(self) -> List[str]:
        """
        Get list of supported MIME types.

        Returns:
            List of MIME types (e.g., ['image/jpeg', 'image/png'])
        """
        pass

    @abstractmethod
    def validate_file(self, file_path: Path) -> bool:
        """
        Validate if file is supported.

        Args:
            file_path: Path to media file

        Returns:
            True if file is valid and supported
        """
        pass

    def cleanup(self):
        """Clean up resources."""
        if hasattr(self._detector, "cleanup"):
            self._detector.cleanup()
        self._detector = None


class ImageAnalyzer(MediaAnalyzer):
    """Analyzer for image AI detection using ClipBased."""

    def __init__(self, model_name: str = "clipbased", device: str = "auto"):
        """
        Initialize image analyzer.

        Args:
            model_name: Model to use ('clipbased', 'ssp')
            device: Device for inference
        """
        super().__init__(device)
        self.model_name = model_name
        self._initialize_detector()

    def _initialize_detector(self):
        """Initialize the ClipBased detector."""
        try:
            from ml.clipbased import ClipBasedImageDetector

            self._detector = ClipBasedImageDetector()
            logger.info("Initialized ClipBased image detector")
        except ImportError as e:
            logger.error("Failed to import ClipBased detector", error=str(e))
            raise RuntimeError("ClipBased detector not available") from e

    async def analyze(self, media_file: MediaFile) -> AnalysisResult:
        """
        Analyze image for AI generation.

        Args:
            media_file: Image file information

        Returns:
            Analysis result with ClipBased detection scores
        """
        if not media_file.has_local_file:
            return AnalysisResult(
                is_ai_generated=None, ai_probability=None, confidence=0.0, model_used=self.model_name, error="Local file not found"
            )

        try:
            import time

            start_time = time.time()

            # Run ClipBased detection
            detection_result = self._detector.detect_image(str(media_file.local_path))

            processing_time = time.time() - start_time

            return AnalysisResult(
                is_ai_generated=detection_result.get("is_ai_generated", False),
                ai_probability=detection_result.get("probability", 0.5),
                confidence=detection_result.get("confidence", 0.0),
                model_used=detection_result.get("model_used", "clipbased"),
                processing_time=processing_time,
                llr_score=detection_result.get("llr_score"),
                metadata=detection_result.get("metadata", {}),
            )

        except Exception as e:
            logger.error("Error analyzing image", file=str(media_file.local_path), error=str(e), exc_info=True)
            return AnalysisResult(is_ai_generated=None, ai_probability=None, confidence=0.0, model_used=self.model_name, error=str(e))

    def get_supported_formats(self) -> List[str]:
        """Get supported image formats."""
        return [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]

    def get_mime_types(self) -> List[str]:
        """Get supported MIME types."""
        return ["image/jpeg", "image/png", "image/bmp", "image/tiff", "image/webp"]

    def validate_file(self, file_path: Path) -> bool:
        """Validate image file."""
        if not file_path.exists():
            return False

        if file_path.suffix.lower() not in self.get_supported_formats():
            return False

        # Check file size (max 50MB for images)
        max_size = 50 * 1024 * 1024
        if file_path.stat().st_size > max_size:
            return False

        return True


class VideoAnalyzer(MediaAnalyzer):
    """Analyzer for video AI detection using SlowFast."""

    def __init__(self, model_name: str = "slowfast_r50", device: str = "auto"):
        """
        Initialize video analyzer.

        Args:
            model_name: Model to use ('slowfast_r50', 'slowfast_r101')
            device: Device for inference
        """
        super().__init__(device)
        self.model_name = model_name
        self._initialize_detector()

    def _initialize_detector(self):
        """Initialize the SlowFast detector and preprocessor."""
        try:
            from ml.slowfast import AIVideoDetector, VideoPreprocessor

            self._detector = AIVideoDetector(model_name=self.model_name, device=self.device)
            self._preprocessor = VideoPreprocessor()
            logger.info("Initialized SlowFast video detector", model=self.model_name)
        except ImportError as e:
            logger.error("Failed to import SlowFast modules", error=str(e))
            raise RuntimeError("SlowFast modules not available") from e

    async def analyze(self, media_file: MediaFile) -> AnalysisResult:
        """
        Analyze video for AI generation.

        Args:
            media_file: Video file information

        Returns:
            Analysis result with SlowFast detection scores
        """
        if not media_file.has_local_file:
            return AnalysisResult(
                is_ai_generated=None, ai_probability=None, confidence=0.0, model_used=self.model_name, error="Local file not found"
            )

        try:
            import time

            start_time = time.time()

            # Preprocess video
            slowfast_input, _ = self._preprocessor.process_video(media_file.local_path)

            # Run SlowFast detection
            raw_result = self._detector.predict(slowfast_input)

            processing_time = time.time() - start_time

            return AnalysisResult(
                is_ai_generated=raw_result.get("is_ai_generated", False),
                ai_probability=raw_result.get("ai_probability", 0.5),
                confidence=raw_result.get("confidence", 0.0),
                model_used=raw_result.get("model_used", self.model_name),
                processing_time=processing_time,
                predictions=raw_result.get("predictions"),
                metadata=raw_result.get("metadata", {}),
            )

        except Exception as e:
            logger.error("Error analyzing video", file=str(media_file.local_path), error=str(e), exc_info=True)
            return AnalysisResult(is_ai_generated=None, ai_probability=None, confidence=0.0, model_used=self.model_name, error=str(e))

    def get_supported_formats(self) -> List[str]:
        """Get supported video formats."""
        return [".mp4", ".avi", ".mov", ".webm", ".mkv", ".flv"]

    def get_mime_types(self) -> List[str]:
        """Get supported MIME types."""
        return ["video/mp4", "video/x-msvideo", "video/quicktime", "video/webm", "video/x-matroska", "video/x-flv"]

    def validate_file(self, file_path: Path) -> bool:
        """Validate video file."""
        if not file_path.exists():
            return False

        if file_path.suffix.lower() not in self.get_supported_formats():
            return False

        # Check file size (max 2GB for videos)
        max_size = 2 * 1024 * 1024 * 1024
        if file_path.stat().st_size > max_size:
            return False

        return True


class MediaAnalyzerFactory:
    """Factory for creating media analyzers."""

    @staticmethod
    def create_analyzer(media_type: MediaType, model_name: Optional[str] = None) -> MediaAnalyzer:
        """
        Create appropriate analyzer for media type.

        Args:
            media_type: Type of media (IMAGE or VIDEO)
            model_name: Optional model name override

        Returns:
            Configured media analyzer
        """
        if media_type == MediaType.IMAGE:
            return ImageAnalyzer(model_name or "clipbased")
        elif media_type == MediaType.VIDEO:
            return VideoAnalyzer(model_name or "slowfast_r50")
        else:
            raise ValueError(f"Unsupported media type: {media_type}")

    @staticmethod
    def create_from_url(url: str, model_name: Optional[str] = None) -> MediaAnalyzer:
        """
        Create analyzer based on URL extension.

        Args:
            url: Media URL
            model_name: Optional model name override

        Returns:
            Appropriate media analyzer
        """
        # Extract extension from URL
        from urllib.parse import urlparse

        path = urlparse(url).path
        extension = Path(path).suffix.lower()

        # Determine media type from extension
        image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
        video_extensions = {".mp4", ".avi", ".mov", ".webm", ".mkv", ".flv"}

        if extension in image_extensions:
            return ImageAnalyzer(model_name or "clipbased")
        elif extension in video_extensions:
            return VideoAnalyzer(model_name or "slowfast_r50")
        else:
            # Default to image analyzer
            return ImageAnalyzer(model_name or "clipbased")
