"""Media Processing Registry

Prevents double media processing across services by tracking media state.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Set

from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MediaProcessingRecord:
    """Track media processing status across services."""

    post_id: str
    media_url: str
    media_type: str
    local_path: Optional[Path] = None
    storage_path: Optional[str] = None
    gemini_uri: Optional[str] = None
    processing_stage: str = "pending"  # pending, downloaded, uploaded, analyzed
    content_hash: Optional[str] = None
    # Detection results
    detection_result: Optional[Dict[str, Any]] = None
    ai_probability: Optional[float] = None
    confidence: Optional[float] = None
    model_used: Optional[str] = None
    detection_error: Optional[str] = None


class MediaProcessingRegistry:
    """Registry to track media processing across all services."""

    def __init__(self):
        self._registry: Dict[str, MediaProcessingRecord] = {}
        self._processed_urls: Set[str] = set()

    def register_media(self, post_id: str, media_url: str, media_type: str) -> str:
        """Register media for processing and return unique key."""
        media_key = f"{post_id}:{media_url}"

        if media_key not in self._registry:
            self._registry[media_key] = MediaProcessingRecord(post_id=post_id, media_url=media_url, media_type=media_type)
            logger.debug("Registered new media for processing", media_key=media_key, media_type=media_type)

        return media_key

    def update_processing_stage(self, media_key: str, stage: str, **kwargs) -> None:
        """Update media processing stage and metadata."""
        if media_key in self._registry:
            record = self._registry[media_key]
            old_stage = record.processing_stage
            record.processing_stage = stage

            # Update optional fields
            for field, value in kwargs.items():
                if hasattr(record, field):
                    setattr(record, field, value)

            logger.debug("Updated media processing stage", media_key=media_key, old_stage=old_stage, new_stage=stage)

    def is_already_processed(self, post_id: str, media_url: str, min_stage: str = "downloaded") -> bool:
        """Check if media has already been processed to a minimum stage."""
        media_key = f"{post_id}:{media_url}"

        if media_key not in self._registry:
            return False

        record = self._registry[media_key]
        stage_order = ["pending", "downloaded", "uploaded", "analyzed"]

        try:
            current_stage_idx = stage_order.index(record.processing_stage)
            min_stage_idx = stage_order.index(min_stage)

            is_processed = current_stage_idx >= min_stage_idx

            logger.debug(
                "Checked media processing status",
                media_key=media_key,
                current_stage=record.processing_stage,
                min_stage=min_stage,
                is_processed=is_processed,
            )

            return is_processed
        except ValueError as e:
            logger.error("Invalid stage in processing check", media_key=media_key, stage=record.processing_stage, error=str(e))
            return False

    def get_processed_media_path(self, post_id: str, media_url: str) -> Optional[Path]:
        """Get local path for already processed media."""
        media_key = f"{post_id}:{media_url}"

        if media_key in self._registry:
            path = self._registry[media_key].local_path
            logger.debug("Retrieved media path", media_key=media_key, path=str(path) if path else None)
            return path

        return None

    def get_processed_media_info(self, post_id: str, media_url: str) -> Optional[MediaProcessingRecord]:
        """Get complete processing record for media."""
        media_key = f"{post_id}:{media_url}"
        return self._registry.get(media_key)

    def update_detection_results(
        self,
        media_key: str,
        ai_probability: float,
        confidence: float,
        model_used: str,
        detection_result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update media detection results."""
        if media_key in self._registry:
            record = self._registry[media_key]
            record.ai_probability = ai_probability
            record.confidence = confidence
            record.model_used = model_used
            record.detection_result = detection_result
            record.detection_error = error

            # Mark as analyzed if successful
            if error is None:
                record.processing_stage = "analyzed"

            logger.debug(
                "Updated detection results",
                media_key=media_key,
                ai_probability=ai_probability,
                confidence=confidence,
                model_used=model_used,
            )

    def get_detection_summary(self, post_id: str) -> Dict[str, Any]:
        """Get detection summary for all media in a post."""
        post_media = []
        for key, record in self._registry.items():
            if record.post_id == post_id:
                post_media.append(
                    {
                        "url": record.media_url,
                        "type": record.media_type,
                        "stage": record.processing_stage,
                        "ai_probability": record.ai_probability,
                        "confidence": record.confidence,
                        "model_used": record.model_used,
                        "has_error": record.detection_error is not None,
                    }
                )

        # Calculate aggregates
        analyzed = [m for m in post_media if m["ai_probability"] is not None]
        if analyzed:
            avg_ai_prob = sum(m["ai_probability"] for m in analyzed) / len(analyzed)
            avg_confidence = sum(m["confidence"] for m in analyzed) / len(analyzed)
        else:
            avg_ai_prob = None
            avg_confidence = None

        return {
            "post_id": post_id,
            "total_media": len(post_media),
            "analyzed_count": len(analyzed),
            "avg_ai_probability": avg_ai_prob,
            "avg_confidence": avg_confidence,
            "media_details": post_media,
        }

    def get_registry_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        stages = {}
        detected_count = 0
        error_count = 0

        for record in self._registry.values():
            stage = record.processing_stage
            stages[stage] = stages.get(stage, 0) + 1

            if record.ai_probability is not None:
                detected_count += 1
            if record.detection_error is not None:
                error_count += 1

        return {"total_media": len(self._registry), "detected": detected_count, "errors": error_count, "by_stage": stages}

    def clear_registry(self) -> None:
        """Clear the registry (for testing or cleanup)."""
        cleared_count = len(self._registry)
        self._registry.clear()
        self._processed_urls.clear()
        logger.info("Cleared media registry", cleared_count=cleared_count)


# Global registry instance
media_registry = MediaProcessingRegistry()
