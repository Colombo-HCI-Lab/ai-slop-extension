"""
High-level detection service that orchestrates video processing and model inference.
Adds singleton, concurrency limits, timeouts, and retries.
"""

import asyncio
import concurrent.futures
import time
from pathlib import Path
from typing import Dict, List, Optional, Union
from uuid import UUID, uuid4

from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings
from schemas.video_detection import DetectionResult, Prediction, VideoInfo, DetectionResponse
from slowfast_detection import AIVideoDetector, VideoPreprocessor
from utils.logging import get_logger

logger = get_logger(__name__)


class DetectionService:
    """High-level service for video AI detection."""

    def __init__(self, model_name: str = None, device: str = None):
        """
        Initialize detection service.

        Args:
            model_name: Name of the model to use
            device: Device for inference
        """
        self.model_name = model_name or settings.default_model
        self.device = device or settings.device

        # Initialize components
        self.preprocessor = VideoPreprocessor()
        self.detector = AIVideoDetector(model_name=self.model_name, device=self.device)
        self._sem = asyncio.Semaphore(settings.video_max_concurrency)
        # Dedicated executors so CPU-heavy decode doesn't block light ops
        self._heavy_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=settings.video_heavy_threads, thread_name_prefix="vid-heavy"
        )
        self._light_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=settings.detection_light_threads, thread_name_prefix="vid-light"
        )

        logger.info("DetectionService initialized", model=self.model_name, device=self.device)

    async def process_video_file_async(
        self,
        video_path: Union[str, Path],
        top_k: Optional[int] = None,
        job_id: UUID = None,
        model_name: Optional[str] = None,
        threshold: Optional[float] = None,
    ) -> DetectionResponse:
        """
        Process a video file for AI generation detection.

        Args:
            video_path: Path to video file
            top_k: Number of top predictions to return
            job_id: Optional job ID for tracking

        Returns:
            Detection response with results
        """
        start_time = time.time()
        job_id = job_id or uuid4()
        top_k = top_k or settings.top_k_predictions

        video_path = Path(video_path)

        try:
            logger.info("Starting video processing", video_path=str(video_path), job_id=str(job_id), model=self.model_name)

            # Switch model for this call if requested
            if model_name and model_name != self.model_name:
                temp_detector = AIVideoDetector(model_name=model_name, device=self.device)
            else:
                temp_detector = self.detector

            # Get video metadata (CPU-bound), run in thread
            loop = asyncio.get_running_loop()
            video_info_dict = await loop.run_in_executor(self._light_executor, self.preprocessor.get_video_info, video_path)
            video_info = VideoInfo(
                filename=video_path.name,
                duration=video_info_dict.get("duration"),
                fps=video_info_dict.get("fps"),
                resolution=video_info_dict.get("resolution"),
                file_size=video_path.stat().st_size if video_path.exists() else None,
            )

            # Process video (CPU-intensive I/O) and run detection with concurrency + timeout + retry
            @retry(
                stop=stop_after_attempt(settings.detection_retry_max_attempts),
                wait=wait_exponential(multiplier=settings.detection_retry_backoff_base, min=0.5, max=8),
                reraise=True,
            )
            def _infer():
                slowfast_input, _ = self.preprocessor.process_video(video_path)
                if threshold is not None and hasattr(temp_detector, "set_threshold"):
                    temp_detector.set_threshold(threshold)
                return temp_detector.predict(slowfast_input)

            async with self._sem:
                loop = asyncio.get_running_loop()
                raw_result = await asyncio.wait_for(
                    loop.run_in_executor(self._heavy_executor, _infer),
                    timeout=settings.detection_timeout_seconds,
                )

            # Adapt result format for service compatibility
            ai_result = {
                "is_ai_generated": raw_result["is_ai_generated"],
                "confidence": raw_result["confidence"],
                "predictions": [
                    {
                        "class_name": "AI-generated" if raw_result["is_ai_generated"] else "Real",
                        "probability": raw_result["ai_probability"],
                        "class_index": 1 if raw_result["is_ai_generated"] else 0,
                    }
                ],
            }

            # Convert predictions to schema format
            predictions = [
                Prediction(class_name=pred["class_name"], probability=pred["probability"], class_index=pred["class_index"])
                for pred in ai_result["predictions"][:top_k]
            ]

            processing_time = time.time() - start_time

            # Create detection result
            detection_result = DetectionResult(
                is_ai_generated=ai_result["is_ai_generated"],
                confidence=ai_result["confidence"],
                model_used=model_name or self.model_name,
                processing_time=processing_time,
                top_predictions=predictions,
            )

            response = DetectionResponse(
                status="completed",
                video_info=video_info,
                detection_result=detection_result,
                created_at=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(start_time)),
            )

            logger.info(
                "Detection completed",
                video_name=video_path.name,
                processing_time=round(processing_time, 2),
                is_ai_generated=ai_result["is_ai_generated"],
                confidence=round(ai_result["confidence"], 3),
                job_id=str(job_id),
            )

            return response

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                "Detection failed",
                video_name=video_path.name,
                error=str(e),
                processing_time=round(processing_time, 2),
                job_id=str(job_id),
                exc_info=True,
            )

            # Create error response
            video_info = VideoInfo(filename=video_path.name, file_size=video_path.stat().st_size if video_path.exists() else None)

            return DetectionResponse(
                status="failed",
                video_info=video_info,
                detection_result=None,
                created_at=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(start_time)),
            )

    def get_supported_formats(self) -> List[str]:
        """Get list of supported video formats."""
        return settings.allowed_extensions

    def get_model_info(self) -> Dict:
        """Get information about the current model."""
        model_info = self.detector.get_model_info()
        model_info.update(
            {
                "supported_formats": self.get_supported_formats(),
                "max_file_size": settings.max_file_size,
                "processing_params": {
                    "num_frames": self.preprocessor.num_frames,
                    "crop_size": self.preprocessor.crop_size,
                    "side_size": self.preprocessor.side_size,
                    "alpha": self.preprocessor.alpha,
                },
            }
        )
        return model_info

    def validate_video_file(self, file_path: Union[str, Path]) -> bool:
        """
        Validate if a video file is supported.

        Args:
            file_path: Path to video file

        Returns:
            True if file is valid and supported
        """
        file_path = Path(file_path)

        # Check if file exists
        if not file_path.exists():
            return False

        # Check file extension
        if file_path.suffix.lower() not in settings.allowed_extensions:
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
        self.detector.set_threshold(threshold)
        logger.info("Detection threshold updated", threshold=threshold)

    def cleanup(self):
        """Clean up service resources."""
        if hasattr(self, "detector"):
            self.detector.cleanup()
        logger.info("DetectionService cleaned up", model=self.model_name)
        # Shut down executors
        try:
            self._heavy_executor.shutdown(wait=False, cancel_futures=True)
            self._light_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    # --- Singleton support ---
    _instance: Optional["DetectionService"] = None

    @classmethod
    def get_instance(cls) -> "DetectionService":
        if cls._instance is None:
            cls._instance = DetectionService()
        return cls._instance
