"""
High-level image detection service that orchestrates image processing and model inference.
Adds singleton, concurrency limits, timeouts, and retries.
"""

import asyncio
import concurrent.futures
import time
from pathlib import Path
from typing import Dict, List, Union, Optional, Tuple
from uuid import UUID, uuid4

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.config import settings
from schemas.image_detection import ImageDetectionResult, ImageInfo, ImageDetectionResponse
from utils.logging import get_logger

logger = get_logger(__name__)


class ImageDetectionService:
    """High-level service for image AI detection."""

    def __init__(self, model_name: str = None, device: str = None):
        """
        Initialize image detection service.

        Args:
            model_name: Name of the model to use
            device: Device for inference
        """
        self.model_name = model_name or settings.default_image_model
        self.device = device or settings.device
        self.detector = None
        self.actual_model = None
        self._sem = asyncio.Semaphore(settings.image_max_concurrency)
        # Dedicated executors so heavy jobs don't block light tasks
        self._heavy_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=settings.image_heavy_threads, thread_name_prefix="img-heavy"
        )
        self._light_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=settings.detection_light_threads, thread_name_prefix="img-light"
        )

        logger.info("ImageDetectionService initialized", model=self.model_name, device=self.device)

    def _get_detector(self, model_name: str = "auto") -> Tuple[object, str]:
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
                    logger.warning(
                        "SSP detector not available, falling back to ClipBased", requested_model=model_name, fallback_model="clipbased"
                    )
                    from clipbased_detection import ClipBasedImageDetector

                    return ClipBasedImageDetector(), "clipbased"
            else:
                raise ValueError(f"Unknown model: {model_name}")
        except ImportError as e:
            logger.error("Failed to import image detector", model_name=model_name, error=str(e), exc_info=True)
            raise RuntimeError("Image detection models not available")

    async def process_image_file_async(
        self, image_path: Union[str, Path], threshold: Optional[float] = None, job_id: UUID = None
    ) -> ImageDetectionResponse:
        """
        Process an image file for AI generation detection.

        Args:
            image_path: Path to image file
            threshold: Detection threshold
            job_id: Optional job ID for tracking

        Returns:
            Detection response with results
        """
        start_time = time.time()
        job_id = job_id or uuid4()
        threshold = threshold if threshold is not None else 0.0

        image_path = Path(image_path)

        try:
            logger.info("Starting image processing", image_path=str(image_path), job_id=str(job_id), model=self.model_name)

            # Get detector
            detector, actual_model = self._get_detector(self.model_name)
            self.detector = detector
            self.actual_model = actual_model

            # Get image metadata
            file_size = image_path.stat().st_size if image_path.exists() else None
            image_info = ImageInfo(
                filename=image_path.name,
                file_size=file_size,
                format=image_path.suffix.lower() if image_path.suffix else None,
            )

            # Run detection with concurrency + timeout + retry in thread
            @retry(
                stop=stop_after_attempt(settings.detection_retry_max_attempts),
                wait=wait_exponential(multiplier=settings.detection_retry_backoff_base, min=0.5, max=8),
                reraise=True,
            )
            def _infer():
                if hasattr(detector, "detect_image"):
                    return detector.detect_image(str(image_path), threshold=threshold)
                return detector.detect(str(image_path))

            async with self._sem:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(self._heavy_executor, _infer),
                    timeout=settings.detection_timeout_seconds,
                )

            # Update image info with detection metadata
            if result.get("metadata", {}).get("image_size"):
                image_info.size = str(result["metadata"]["image_size"])

            processing_time = time.time() - start_time

            # Create detection result
            detection_result = ImageDetectionResult(
                is_ai_generated=result.get("is_ai_generated", False),
                confidence=result.get("confidence", 0.0),
                model_used=actual_model,
                processing_time=processing_time,
                llr_score=result.get("llr_score"),
                probability=result.get("probability"),
                threshold=result.get("threshold"),
                metadata=result.get("metadata", {}),
            )

            response = ImageDetectionResponse(
                status="completed",
                image_info=image_info,
                detection_result=detection_result,
                created_at=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(start_time)),
            )

            logger.info(
                "Image detection completed",
                image_name=image_path.name,
                processing_time=round(processing_time, 2),
                is_ai_generated=result.get("is_ai_generated", False),
                confidence=round(result.get("confidence", 0.0), 3),
                job_id=str(job_id),
            )

            return response

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                "Image detection failed",
                image_name=image_path.name,
                error=str(e),
                processing_time=round(processing_time, 2),
                job_id=str(job_id),
                exc_info=True,
            )

            # Create error response
            image_info = ImageInfo(filename=image_path.name, file_size=image_path.stat().st_size if image_path.exists() else None)

            return ImageDetectionResponse(
                status="failed",
                image_info=image_info,
                detection_result=None,
                created_at=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(start_time)),
            )

    def get_supported_formats(self) -> List[str]:
        """Get list of supported image formats."""
        return [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]

    def get_available_models(self) -> List[str]:
        """Get list of available image detection models."""
        models = []

        # Check ClipBased
        try:
            from clipbased_detection import ClipBasedImageDetector
            from clipbased_detection.config import config

            models.extend(config.get_available_models())
        except ImportError:
            logger.warning("ClipBased models not available")

        # Check SSP
        try:
            from slowfast_detection.image_detection import SSPImageDetector

            models.append("ssp")
        except ImportError:
            logger.warning("SSP model not available")

        # Add auto option
        if models:
            models.insert(0, "auto")

        return models

    def get_model_info(self) -> Dict:
        """Get information about the current model."""
        model_info = {
            "name": self.model_name,
            "actual_model": getattr(self, "actual_model", None),
            "supported_formats": self.get_supported_formats(),
            "max_file_size": settings.max_file_size,
            "available_models": self.get_available_models(),
        }

        if hasattr(self.detector, "get_model_info"):
            model_specific_info = self.detector.get_model_info()
            model_info.update(model_specific_info)

        return model_info

    def validate_image_file(self, file_path: Union[str, Path]) -> bool:
        """
        Validate if an image file is supported.

        Args:
            file_path: Path to image file

        Returns:
            True if file is valid and supported
        """
        file_path = Path(file_path)

        # Check if file exists
        if not file_path.exists():
            return False

        # Check file extension
        supported_formats = self.get_supported_formats()
        if file_path.suffix.lower() not in supported_formats:
            return False

        # Check file size
        if file_path.stat().st_size > settings.max_file_size:
            return False

        return True

    def set_threshold(self, threshold: float):
        """
        Set AI detection threshold.

        Args:
            threshold: Threshold value for AI classification
        """
        if hasattr(self.detector, "set_threshold"):
            self.detector.set_threshold(threshold)
        logger.info("Detection threshold updated", threshold=threshold)

    def cleanup(self):
        """Clean up service resources."""
        if hasattr(self.detector, "cleanup"):
            self.detector.cleanup()
        logger.info("ImageDetectionService cleaned up", model=self.model_name)
        # Shut down executors
        try:
            self._heavy_executor.shutdown(wait=False, cancel_futures=True)
            self._light_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    # --- Singleton support ---
    _instance: Optional["ImageDetectionService"] = None

    @classmethod
    def get_instance(cls) -> "ImageDetectionService":
        if cls._instance is None:
            cls._instance = ImageDetectionService()
        return cls._instance
