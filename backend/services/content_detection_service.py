"""Content AI detection service for text, images, and videos."""

import asyncio
import logging
import tempfile
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from schemas.content_detection import ContentDetectionRequest, ContentDetectionResponse
from schemas.text_detection import DetectRequest
from services.text_detection_service import TextDetectionService

logger = logging.getLogger(__name__)


class ContentDetectionService:
    """Service for detecting AI-generated content across text, images, and videos."""

    def __init__(self):
        """Initialize the content detection service."""
        self.text_service = TextDetectionService()

    async def detect(
        self,
        request: ContentDetectionRequest,
        db: AsyncSession,
        use_cache: bool = True,
    ) -> ContentDetectionResponse:
        """
        Detect AI-generated content across all modalities.

        Args:
            request: Detection request with content, image URLs, and video URLs
            db: Database session
            use_cache: Whether to use cached results

        Returns:
            Detection response with aggregated verdict and detailed analysis
        """
        logger.info(f"Starting multi-modal analysis for post {request.post_id}")

        # Check cache first for text analysis
        if use_cache:
            # Convert content detection request to text detection request for cache check
            text_request = DetectRequest(post_id=request.post_id, content=request.content, author=request.author, metadata=request.metadata)
            text_result = await self.text_service.detect(text_request, db, use_cache=True)
            if hasattr(text_result, "debug_info") and text_result.debug_info.get("from_cache"):
                logger.info(f"Using cached text result for post {request.post_id}")

                # For cached results, still analyze media if present
                image_results, image_ai_prob, image_conf = await self._analyze_images(request.image_urls) if request.image_urls else ([], None, None)
                video_results, video_ai_prob, video_conf = await self._analyze_videos(request.video_urls) if request.video_urls else ([], None, None)

                # Create aggregated response
                return self._create_aggregated_response(
                    request.post_id, text_result, image_results, video_results,
                    image_ai_prob, image_conf, video_ai_prob, video_conf
                )

        # Analyze all modalities in parallel
        tasks = []

        # Text analysis
        tasks.append(self._analyze_text(request, db))

        # Image analysis (if image URLs provided)
        if request.image_urls:
            tasks.append(self._analyze_images(request.image_urls))
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0, result=([], None, None))))

        # Video analysis (if video URLs provided)
        if request.video_urls:
            tasks.append(self._analyze_videos(request.video_urls))
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0, result=([], None, None))))

        # Execute all analyses
        text_result, (image_results, image_ai_prob, image_conf), (video_results, video_ai_prob, video_conf) = await asyncio.gather(*tasks)

        return self._create_aggregated_response(
            request.post_id, text_result, image_results, video_results,
            image_ai_prob, image_conf, video_ai_prob, video_conf
        )

    async def _analyze_text(self, request: ContentDetectionRequest, db: AsyncSession):
        """Analyze text content."""
        # Convert content detection request to text detection request
        text_request = DetectRequest(post_id=request.post_id, content=request.content, author=request.author, metadata=request.metadata)
        return await self.text_service.detect(text_request, db, use_cache=False)

    async def _analyze_images(self, image_urls: List[str]) -> tuple[List[Dict[str, Any]], Optional[float], Optional[float]]:
        """
        Analyze images from URLs.
        
        Returns:
            Tuple of (image_results, ai_probability, analysis_confidence)
        """
        if not image_urls:
            return [], None, None

        logger.info(f"Analyzing {len(image_urls)} images")
        image_results = []
        
        # For blocked images, we can't determine AI probability
        ai_probability = None
        analysis_confidence = None

        for i, url in enumerate(image_urls):
            try:
                # Note: Facebook images are typically blocked by CORS/authentication
                # For now, we'll return a placeholder result indicating the limitation
                result = {
                    "url": url,
                    "status": "blocked",
                    "reason": "Facebook CDN prevents direct access",
                    "is_ai_generated": None,
                    "ai_probability": None,
                    "confidence": 0.0,
                    "model_used": "clipbased",
                    "error": "403 Forbidden - Cannot access Facebook CDN images directly",
                }

                # In a production system, you might:
                # 1. Use a proxy service
                # 2. Extract images via browser automation
                # 3. Have the client send image data directly

                logger.warning(f"Cannot analyze Facebook image URL: {url}")
                image_results.append(result)

            except Exception as e:
                logger.error(f"Error analyzing image {url}: {e}")
                image_results.append({
                    "url": url, 
                    "status": "error", 
                    "error": str(e), 
                    "is_ai_generated": None, 
                    "ai_probability": None,
                    "confidence": 0.0
                })

        return image_results, ai_probability, analysis_confidence

    async def _analyze_videos(self, video_urls: List[str]) -> tuple[List[Dict[str, Any]], Optional[float], Optional[float]]:
        """
        Analyze videos from URLs.
        
        Returns:
            Tuple of (video_results, ai_probability, analysis_confidence)
        """
        if not video_urls:
            return [], None, None

        logger.info(f"Analyzing {len(video_urls)} videos")
        video_results = []
        
        # For blocked videos, we can't determine AI probability
        ai_probability = None
        analysis_confidence = None

        for url in video_urls:
            try:
                # Similar limitation as images - Facebook videos are typically blocked
                result = {
                    "url": url,
                    "status": "blocked",
                    "reason": "Facebook CDN prevents direct access",
                    "is_ai_generated": None,
                    "ai_probability": None,
                    "confidence": 0.0,
                    "model_used": "slowfast_r50",
                    "error": "403 Forbidden - Cannot access Facebook CDN videos directly",
                }

                logger.warning(f"Cannot analyze Facebook video URL: {url}")
                video_results.append(result)

            except Exception as e:
                logger.error(f"Error analyzing video {url}: {e}")
                video_results.append({
                    "url": url, 
                    "status": "error", 
                    "error": str(e), 
                    "is_ai_generated": None, 
                    "ai_probability": None,
                    "confidence": 0.0
                })

        return video_results, ai_probability, analysis_confidence

    def _create_aggregated_response(
        self, 
        post_id: str, 
        text_result, 
        image_results: List[Dict[str, Any]], 
        video_results: List[Dict[str, Any]],
        image_ai_probability: Optional[float] = None,
        image_confidence: Optional[float] = None,
        video_ai_probability: Optional[float] = None,
        video_confidence: Optional[float] = None
    ) -> ContentDetectionResponse:
        """Create aggregated response from all modality analyses."""

        # For now, use text analysis as primary verdict
        # In the future, this could implement sophisticated fusion logic
        overall_verdict = text_result.verdict
        overall_confidence = text_result.confidence

        # Count successful media analyses
        successful_images = len([r for r in image_results if r.get("status") == "success"])
        successful_videos = len([r for r in video_results if r.get("status") == "success"])

        # Create explanation
        explanations = [text_result.explanation]

        if image_results:
            blocked_images = len([r for r in image_results if r.get("status") == "blocked"])
            if blocked_images > 0:
                explanations.append(f"Unable to analyze {blocked_images} images (Facebook CDN blocked)")
            if successful_images > 0:
                explanations.append(f"Analyzed {successful_images} images")

        if video_results:
            blocked_videos = len([r for r in video_results if r.get("status") == "blocked"])
            if blocked_videos > 0:
                explanations.append(f"Unable to analyze {blocked_videos} videos (Facebook CDN blocked)")
            if successful_videos > 0:
                explanations.append(f"Analyzed {successful_videos} videos")

        # Create comprehensive response
        return ContentDetectionResponse(
            post_id=post_id,
            verdict=overall_verdict,
            confidence=overall_confidence,
            explanation=" | ".join(explanations),
            timestamp=datetime.utcnow().isoformat(),
            text_ai_probability=getattr(text_result, 'text_ai_probability', None),
            text_confidence=getattr(text_result, 'text_confidence', None),
            image_ai_probability=image_ai_probability,
            image_confidence=image_confidence,
            video_ai_probability=video_ai_probability,
            video_confidence=video_confidence,
            text_analysis={"verdict": text_result.verdict, "confidence": text_result.confidence, "explanation": text_result.explanation},
            image_analysis=image_results if image_results else [],
            video_analysis=video_results if video_results else [],
            debug_info={
                "total_images": len(image_results),
                "total_videos": len(video_results),
                "successful_images": successful_images,
                "successful_videos": successful_videos,
                "multimodal_analysis": True,
            },
        )
