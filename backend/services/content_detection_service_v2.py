"""Improved content AI detection service using unified media processing."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.media_registry import media_registry
from schemas.content_detection import ContentDetectionRequest, ContentDetectionResponse
from schemas.text_detection import DetectRequest
from services.text_detection_service import TextDetectionService
from services.unified_media_service import UnifiedMediaService
from services.media_analyzer import MediaType
from utils.logging import get_logger

logger = get_logger(__name__)


class ContentDetectionServiceV2:
    """Improved service for detecting AI-generated content with unified media processing."""

    def __init__(self):
        """Initialize the content detection service."""
        self.text_service = TextDetectionService.get_instance()
        self.media_service = UnifiedMediaService(max_workers=4)

    async def detect(
        self,
        request: ContentDetectionRequest,
        db: AsyncSession,
    ) -> ContentDetectionResponse:
        """
        Detect AI-generated content across all modalities with unified processing.

        Args:
            request: Detection request with content, image URLs, and video URLs
            db: Database session

        Returns:
            Detection response with aggregated verdict and detailed analysis
        """
        # Check for cached results first
        cached_response = await self._check_cached_results(request.post_id, db)
        if cached_response:
            return cached_response

        logger.info(
            "Starting unified multi-modal analysis",
            post_id=request.post_id,
            has_images=bool(request.image_urls),
            has_videos=bool(request.video_urls),
            content_length=len(request.content) if request.content else 0,
        )

        # Get media information from database
        media_info = await self._get_post_media_info(request.post_id, db)

        # Run all analyses in parallel
        analysis_tasks = []

        # Text analysis
        analysis_tasks.append(self._analyze_text(request, db))

        # Image analysis using unified service
        if request.image_urls:
            analysis_tasks.append(
                self.media_service.analyze_media_batch(request.image_urls, MediaType.IMAGE, request.post_id, media_info, db)
            )
        else:
            analysis_tasks.append(self._create_empty_media_result())

        # Video analysis using unified service
        if request.video_urls:
            analysis_tasks.append(
                self.media_service.analyze_media_batch(request.video_urls, MediaType.VIDEO, request.post_id, media_info, db)
            )
        else:
            analysis_tasks.append(self._create_empty_media_result())

        # Execute all analyses concurrently
        results = await asyncio.gather(*analysis_tasks)
        text_result = results[0]
        image_results, image_ai_prob, image_conf = results[1]
        video_results, video_ai_prob, video_conf = results[2]

        # Update database with analysis results
        await self._update_post_with_results(request.post_id, text_result, image_ai_prob, image_conf, video_ai_prob, video_conf, db)

        # Create and return aggregated response
        return self._create_aggregated_response(
            request.post_id, text_result, image_results, video_results, image_ai_prob, image_conf, video_ai_prob, video_conf
        )

    async def _check_cached_results(self, post_id: str, db: AsyncSession) -> Optional[ContentDetectionResponse]:
        """
        Check for cached detection results.

        Args:
            post_id: Facebook post ID
            db: Database session

        Returns:
            Cached response if available, None otherwise
        """
        from sqlalchemy import select
        from db.models import Post

        result = await db.execute(select(Post).where(Post.post_id == post_id))
        post = result.scalar_one_or_none()

        # Return cached results if post is fully processed
        if post and post.verdict != "pending":
            logger.info(
                "Returning cached detection results",
                post_id=post_id,
                verdict=post.verdict,
                confidence=post.confidence,
            )

            return ContentDetectionResponse(
                post_id=post_id,
                verdict=post.verdict,
                confidence=post.confidence,
                explanation=post.explanation,
                text_ai_probability=post.text_ai_probability,
                text_confidence=post.text_confidence,
                image_ai_probability=post.image_ai_probability,
                image_confidence=post.image_confidence,
                video_ai_probability=post.video_ai_probability,
                video_confidence=post.video_confidence,
                image_analysis=[],  # Could retrieve from post_media if needed
                video_analysis=[],  # Could retrieve from post_media if needed
                debug_info={"from_cache": True},
                timestamp=datetime.now().isoformat(),
            )

        return None

    async def _get_post_media_info(self, post_id: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Get media information from database for the post.

        Args:
            post_id: Facebook post ID
            db: Database session

        Returns:
            Dictionary mapping URLs to media information
        """
        from sqlalchemy import select
        from db.models import PostMedia

        result = await db.execute(select(PostMedia).where(PostMedia.post_id == post_id))
        media_records = result.scalars().all()

        media_info = {}
        for media in media_records:
            media_info[media.media_url] = {
                "media_id": media.id,
                "storage_path": media.storage_path,
                "storage_type": media.storage_type,
                "gemini_uri": media.gemini_file_uri,
                "media_type": media.media_type,
                "content_hash": media.content_hash,
            }

        logger.debug("Retrieved media info from database", post_id=post_id, media_count=len(media_info))

        return media_info

    async def _analyze_text(self, request: ContentDetectionRequest, db: AsyncSession):
        """
        Analyze text content for AI generation.

        Args:
            request: Detection request
            db: Database session

        Returns:
            Text analysis result
        """
        text_request = DetectRequest(post_id=request.post_id, content=request.content, author=request.author, metadata=request.metadata)
        return await self.text_service.detect(text_request, db)

    async def _create_empty_media_result(self):
        """
        Create empty result for missing media type.

        Returns:
            Tuple of (empty_list, None, None)
        """
        await asyncio.sleep(0)  # Yield to event loop
        return [], None, None

    async def _update_post_with_results(
        self,
        post_id: str,
        text_result: Any,
        image_ai_probability: Optional[float],
        image_confidence: Optional[float],
        video_ai_probability: Optional[float],
        video_confidence: Optional[float],
        db: AsyncSession,
    ) -> None:
        """
        Update post in database with all analysis results.

        Args:
            post_id: Facebook post ID
            text_result: Text analysis result
            image_ai_probability: Average AI probability for images
            image_confidence: Average confidence for images
            video_ai_probability: Average AI probability for videos
            video_confidence: Average confidence for videos
            db: Database session
        """
        from sqlalchemy import select
        from db.models import Post

        result = await db.execute(select(Post).where(Post.post_id == post_id))
        post = result.scalar_one_or_none()

        if post:
            # Update with all analysis results
            post.verdict = text_result.verdict
            post.confidence = text_result.confidence
            post.explanation = text_result.explanation
            post.text_ai_probability = getattr(text_result, "text_ai_probability", None)
            post.text_confidence = getattr(text_result, "text_confidence", None)
            post.image_ai_probability = image_ai_probability
            post.image_confidence = image_confidence
            post.video_ai_probability = video_ai_probability
            post.video_confidence = video_confidence

            await db.commit()

            logger.info(
                "Updated post with all analysis results",
                post_id=post_id,
                verdict=post.verdict,
                confidence=post.confidence,
                has_image_analysis=image_ai_probability is not None,
                has_video_analysis=video_ai_probability is not None,
            )
        else:
            logger.warning("Post not found for updating results", post_id=post_id)

    def _create_aggregated_response(
        self,
        post_id: str,
        text_result: Any,
        image_results: List[Dict[str, Any]],
        video_results: List[Dict[str, Any]],
        image_ai_probability: Optional[float] = None,
        image_confidence: Optional[float] = None,
        video_ai_probability: Optional[float] = None,
        video_confidence: Optional[float] = None,
    ) -> ContentDetectionResponse:
        """
        Create aggregated response from all modality analyses.

        Args:
            post_id: Facebook post ID
            text_result: Text analysis result
            image_results: List of image analysis results
            video_results: List of video analysis results
            image_ai_probability: Average AI probability for images
            image_confidence: Average confidence for images
            video_ai_probability: Average AI probability for videos
            video_confidence: Average confidence for videos

        Returns:
            Aggregated detection response
        """
        # Use weighted verdict calculation if multiple modalities present
        overall_verdict, overall_confidence = self._calculate_overall_verdict(
            text_result, image_ai_probability, image_confidence, video_ai_probability, video_confidence
        )

        # Count successful analyses
        successful_images = len([r for r in image_results if r.get("status") == "success"])
        successful_videos = len([r for r in video_results if r.get("status") == "success"])

        # Build explanation
        explanations = []
        if text_result.explanation:
            explanations.append(text_result.explanation)

        if image_results:
            if successful_images > 0:
                explanations.append(f"Analyzed {successful_images} images")
            failed_images = len(image_results) - successful_images
            if failed_images > 0:
                explanations.append(f"{failed_images} images failed analysis")

        if video_results:
            if successful_videos > 0:
                explanations.append(f"Analyzed {successful_videos} videos")
            failed_videos = len(video_results) - successful_videos
            if failed_videos > 0:
                explanations.append(f"{failed_videos} videos failed analysis")

        # Create comprehensive response
        return ContentDetectionResponse(
            post_id=post_id,
            verdict=overall_verdict,
            confidence=overall_confidence,
            explanation=" | ".join(explanations) if explanations else "Analysis complete",
            timestamp=datetime.utcnow().isoformat(),
            text_ai_probability=getattr(text_result, "text_ai_probability", None),
            text_confidence=getattr(text_result, "text_confidence", None),
            image_ai_probability=image_ai_probability,
            image_confidence=image_confidence,
            video_ai_probability=video_ai_probability,
            video_confidence=video_confidence,
            text_analysis={"verdict": text_result.verdict, "confidence": text_result.confidence, "explanation": text_result.explanation},
            image_analysis=image_results,
            video_analysis=video_results,
            debug_info={
                "total_images": len(image_results),
                "total_videos": len(video_results),
                "successful_images": successful_images,
                "successful_videos": successful_videos,
                "multimodal_analysis": True,
                "unified_processing": True,
                "from_cache": False,
            },
        )

    def _calculate_overall_verdict(
        self,
        text_result: Any,
        image_ai_prob: Optional[float],
        image_conf: Optional[float],
        video_ai_prob: Optional[float],
        video_conf: Optional[float],
    ) -> Tuple[str, float]:
        """
        Calculate overall verdict using weighted combination of modalities.

        Args:
            text_result: Text analysis result
            image_ai_prob: Image AI probability
            image_conf: Image confidence
            video_ai_prob: Video AI probability
            video_conf: Video confidence

        Returns:
            Tuple of (verdict, confidence)
        """
        # Collect available modalities with their scores
        modalities = []

        # Text modality
        if hasattr(text_result, "text_ai_probability") and text_result.text_ai_probability is not None:
            modalities.append(
                {
                    "probability": text_result.text_ai_probability,
                    "confidence": text_result.text_confidence or text_result.confidence,
                    "weight": 1.0,  # Text has standard weight
                }
            )

        # Image modality
        if image_ai_prob is not None:
            modalities.append(
                {
                    "probability": image_ai_prob,
                    "confidence": image_conf or 0.5,
                    "weight": 1.2,  # Images slightly more weight
                }
            )

        # Video modality
        if video_ai_prob is not None:
            modalities.append(
                {
                    "probability": video_ai_prob,
                    "confidence": video_conf or 0.5,
                    "weight": 1.5,  # Videos have highest weight
                }
            )

        # If no modalities with scores, use text verdict
        if not modalities:
            return text_result.verdict, text_result.confidence

        # Calculate weighted average
        total_weight = sum(m["weight"] * m["confidence"] for m in modalities)
        if total_weight == 0:
            return text_result.verdict, text_result.confidence

        weighted_probability = sum(m["probability"] * m["weight"] * m["confidence"] for m in modalities) / total_weight

        weighted_confidence = sum(m["confidence"] * m["weight"] for m in modalities) / sum(m["weight"] for m in modalities)

        # Determine verdict based on weighted probability
        if weighted_probability >= 0.7:
            verdict = "ai_slop"
        elif weighted_probability <= 0.3:
            verdict = "human_content"
        else:
            verdict = "uncertain"

        logger.debug(
            "Calculated weighted verdict",
            modality_count=len(modalities),
            weighted_probability=round(weighted_probability, 3),
            weighted_confidence=round(weighted_confidence, 3),
            verdict=verdict,
        )

        return verdict, weighted_confidence
