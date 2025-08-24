"""Content AI detection service for text, images, and videos."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.media_registry import media_registry
from schemas.content_detection import ContentDetectionRequest, ContentDetectionResponse
from schemas.text_detection import DetectRequest
from services.text_detection_service import TextDetectionService
from utils.logging import get_logger

logger = get_logger(__name__)


class ContentDetectionService:
    """Service for detecting AI-generated content across text, images, and videos."""

    def __init__(self):
        """Initialize the content detection service."""
        self.text_service = TextDetectionService()

    async def detect(
        self,
        request: ContentDetectionRequest,
        db: AsyncSession,
    ) -> ContentDetectionResponse:
        """
        Detect AI-generated content across all modalities.

        Args:
            request: Detection request with content, image URLs, and video URLs
            db: Database session

        Returns:
            Detection response with aggregated verdict and detailed analysis
        """
        # Check if post has already been fully processed
        from sqlalchemy import select

        from models import Post

        result = await db.execute(select(Post).where(Post.post_id == request.post_id))
        existing_post = result.scalar_one_or_none()

        # If post exists and has been processed (verdict != "pending"), return cached results
        if existing_post and existing_post.verdict != "pending":
            logger.info(
                "Returning cached detection results",
                post_id=request.post_id,
                verdict=existing_post.verdict,
                confidence=existing_post.confidence,
            )

            # Build cached response from database
            from datetime import datetime

            return ContentDetectionResponse(
                post_id=request.post_id,
                verdict=existing_post.verdict,
                confidence=existing_post.confidence,
                explanation=existing_post.explanation,
                text_ai_probability=existing_post.text_ai_probability,
                text_confidence=existing_post.text_confidence,
                image_ai_probability=existing_post.image_ai_probability,
                image_confidence=existing_post.image_confidence,
                video_ai_probability=existing_post.video_ai_probability,
                video_confidence=existing_post.video_confidence,
                image_analysis=[],  # Could retrieve from post_media if needed
                video_analysis=[],  # Could retrieve from post_media if needed
                debug_info={"from_cache": True},
                timestamp=datetime.now().isoformat(),
            )

        logger.info(
            "Starting multi-modal analysis",
            post_id=request.post_id,
            has_images=bool(request.image_urls),
            has_videos=bool(request.video_urls),
            content_length=len(request.content) if request.content else 0,
        )

        # Get media IDs from database for proper tracking
        media_info = await self._get_post_media_info(request.post_id, db)

        # Analyze all modalities in parallel
        tasks = []

        # Text analysis
        tasks.append(self._analyze_text(request, db))

        # Image analysis (if image URLs provided)
        if request.image_urls:
            tasks.append(self._analyze_images(request.image_urls, request.post_id, media_info))
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0, result=([], None, None))))

        # Video analysis (if video URLs provided)
        if request.video_urls:
            tasks.append(self._analyze_videos(request.video_urls, request.post_id, media_info))
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0, result=([], None, None))))

        # Execute all analyses
        text_result, (image_results, image_ai_prob, image_conf), (video_results, video_ai_prob, video_conf) = await asyncio.gather(*tasks)

        # Update the post in database with image and video analysis results
        await self._update_post_with_media_analysis(request.post_id, image_ai_prob, image_conf, video_ai_prob, video_conf, db)

        return self._create_aggregated_response(
            request.post_id, text_result, image_results, video_results, image_ai_prob, image_conf, video_ai_prob, video_conf
        )

    async def _get_post_media_info(self, post_id: str, db: AsyncSession) -> Dict[str, Any]:
        """Get media information from database for the post."""
        from sqlalchemy import select

        from models import PostMedia

        result = await db.execute(select(PostMedia).where(PostMedia.post_id == post_id))
        media_records = result.scalars().all()

        media_info = {}
        for media in media_records:
            # Map URL to media ID and storage path
            media_info[media.media_url] = {
                "media_id": media.id,
                "storage_path": media.storage_path,
                "storage_type": media.storage_type,
                "gemini_uri": media.gemini_file_uri,
                "media_type": media.media_type,
            }

        return media_info

    async def _analyze_text(self, request: ContentDetectionRequest, db: AsyncSession):
        """Analyze text content."""
        # Convert content detection request to text detection request
        text_request = DetectRequest(post_id=request.post_id, content=request.content, author=request.author, metadata=request.metadata)
        return await self.text_service.detect(text_request, db)

    async def _analyze_images(
        self, image_urls: List[str], post_id: str, media_info: Dict[str, Any]
    ) -> tuple[List[Dict[str, Any]], Optional[float], Optional[float]]:
        """
        Analyze images using ClipBased AI detection on locally downloaded images.

        Returns:
            Tuple of (image_results, ai_probability, analysis_confidence)
        """
        if not image_urls:
            return [], None, None

        logger.info("Starting real ClipBased image analysis", image_count=len(image_urls))
        image_results = []

        # Initialize ClipBased detector
        try:
            from clipbased_detection import ClipBasedImageDetector

            detector = ClipBasedImageDetector()
        except ImportError as e:
            logger.error("Failed to import ClipBased detector", error=str(e))
            # Fallback to error results
            for url in image_urls:
                image_results.append(
                    {
                        "url": url,
                        "status": "error",
                        "error": "ClipBased detector not available",
                        "is_ai_generated": None,
                        "ai_probability": None,
                        "confidence": 0.0,
                    }
                )
            return image_results, None, None

        for i, url in enumerate(image_urls):
            try:
                # First, check media registry for already processed image
                if media_registry.is_already_processed(post_id, url, "downloaded"):
                    # Use existing local file from registry
                    registry_record = media_registry.get_processed_media_info(post_id, url)
                    if registry_record and registry_record.local_path and registry_record.local_path.exists():
                        logger.info("Using already processed media for detection", 
                                  url=url[:50], local_path=str(registry_record.local_path))
                        image_file = registry_record.local_path
                    else:
                        logger.warning("Registry shows media processed but local file not found", 
                                     url=url[:50], local_path=str(registry_record.local_path) if registry_record else None)
                        # Fall through to database/fallback lookup
                        image_file = None
                else:
                    # Registry doesn't have this media, check database
                    media_record = media_info.get(url, {})
                    media_id = media_record.get("media_id")
                    storage_path = media_record.get("storage_path")
                    storage_type = media_record.get("storage_type")

                    # Handle different storage types
                    image_file = None
                    if storage_path:
                        if storage_type == "gcs":
                            # Download from GCS to local tmp directory for analysis
                            try:
                                from services.gcs_storage_service import GCSStorageService
                                from pathlib import Path
                                
                                gcs_service = GCSStorageService()
                                gcs_path = gcs_service.gcs_uri_to_path(storage_path)
                                
                                # Generate local path for downloaded file
                                local_path = self._get_local_file_path(post_id, url, "image")
                                local_path.parent.mkdir(parents=True, exist_ok=True)
                                
                                # Download from GCS and save locally
                                data = await gcs_service.download_media(gcs_path)
                                local_path.write_bytes(data)
                                
                                image_file = local_path
                                logger.info("Downloaded image from GCS for analysis", 
                                          url=url[:50], 
                                          gcs_path=gcs_path, 
                                          local_path=str(local_path))
                                          
                            except Exception as e:
                                logger.error("Failed to download image from GCS", 
                                           url=url[:50], 
                                           storage_path=storage_path, 
                                           error=str(e))
                                # Fall through to other fallback methods
                        else:
                            # Local storage
                            from pathlib import Path
                            image_file = Path(storage_path)
                    else:
                        # Fallback to finding file by URL hash if not in database
                        import hashlib

                        from core.config import settings

                        # Generate URL hash to match the downloaded file naming convention
                        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

                        # Construct the expected post media directory
                        post_media_dir = settings.tmp_dir / "posts" / post_id / "media"

                        # Find the image file with this URL hash in the post directory
                        image_file = None
                        if post_media_dir.exists():
                            for image_path in post_media_dir.glob(f"*{url_hash}*"):
                                if image_path.is_file():
                                    image_file = image_path
                                    break

                if not image_file or not image_file.exists():
                    logger.warning("Downloaded image file not found for analysis", url=url[:50])
                    
                    # Fallback: attempt to download if not already processed
                    if not media_registry.is_already_processed(post_id, url, "downloaded"):
                        logger.warning("Media not found in registry, downloading for detection", url=url[:50])
                        # This shouldn't happen in normal flow since FileUploadService should have processed it
                        # but we can handle it as a fallback
                        # For now, log the issue and continue with error
                        
                    image_results.append(
                        {
                            "url": url,
                            "status": "error",
                            "error": "Downloaded image file not found",
                            "is_ai_generated": None,
                            "ai_probability": None,
                            "confidence": 0.0,
                        }
                    )
                    continue

                # Run real ClipBased detection on the downloaded image
                logger.debug("Running ClipBased detection", image_file=str(image_file))
                detection_result = detector.detect_image(str(image_file))

                # Convert ClipBased result format to our expected format
                is_ai_generated = detection_result.get("is_ai_generated", False)
                confidence = detection_result.get("confidence", 0.0)

                # Convert to probability (0.0 = human, 1.0 = AI)
                # ClipBased returns probability directly
                ai_probability = detection_result.get("probability", 0.5)

                # Get media_id from database fallback if not found in first check
                media_id = None
                if not media_registry.is_already_processed(post_id, url, "downloaded"):
                    media_record = media_info.get(url, {})
                    media_id = media_record.get("media_id")

                # Update registry to mark as analyzed
                media_key = f"{post_id}:{url}"
                media_registry.update_processing_stage(media_key, "analyzed")

                result = {
                    "media_id": media_id,  # Include media ID from database
                    "url": url,
                    "status": "success",
                    "reason": "ClipBased AI detection on downloaded image",
                    "is_ai_generated": is_ai_generated,
                    "ai_probability": ai_probability,
                    "confidence": confidence,
                    "model_used": detection_result.get("model_used", "clipbased"),
                    "llr_score": detection_result.get("llr_score"),
                    "processing_time": detection_result.get("processing_time"),
                    "local_file": str(image_file),
                    "error": None,
                }

                logger.info(
                    "ClipBased image analysis completed",
                    url=url,
                    local_file=str(image_file),
                    ai_probability=round(ai_probability, 3),
                    confidence=round(confidence, 3),
                    is_ai_generated=is_ai_generated,
                    llr_score=round(detection_result.get("llr_score", 0.0), 3),
                )
                image_results.append(result)

            except Exception as e:
                logger.error("Error analyzing image with ClipBased", url=url, error=str(e), exc_info=True)
                image_results.append(
                    {"url": url, "status": "error", "error": str(e), "is_ai_generated": None, "ai_probability": None, "confidence": 0.0}
                )

        # Calculate aggregate AI probability and confidence for all images
        ai_probability = None
        analysis_confidence = None

        if image_results:
            successful_results = [r for r in image_results if r.get("status") == "success" and r.get("ai_probability") is not None]
            if successful_results:
                # Average the AI probabilities and confidences
                ai_probability = sum(r["ai_probability"] for r in successful_results) / len(successful_results)
                analysis_confidence = sum(r["confidence"] for r in successful_results) / len(successful_results)
                logger.info(
                    "Aggregate ClipBased image analysis completed",
                    successful_images=len(successful_results),
                    total_images=len(image_results),
                    avg_ai_probability=round(ai_probability, 3),
                    avg_confidence=round(analysis_confidence, 3),
                )
            else:
                logger.warning("No successful image analyses", total_images=len(image_results))

        return image_results, ai_probability, analysis_confidence

    async def _analyze_videos(
        self, video_urls: List[str], post_id: str, media_info: Dict[str, Any]
    ) -> tuple[List[Dict[str, Any]], Optional[float], Optional[float]]:
        """
        Analyze videos using SlowFast AI detection on locally downloaded videos.

        Returns:
            Tuple of (video_results, ai_probability, analysis_confidence)
        """
        if not video_urls:
            return [], None, None

        logger.info("Starting real SlowFast video analysis", video_count=len(video_urls))
        video_results = []

        # Initialize SlowFast detector
        try:
            from slowfast_detection import SlowFastVideoDetector

            detector = SlowFastVideoDetector()
        except ImportError as e:
            logger.error("Failed to import SlowFast detector", error=str(e))
            # Fallback to error results
            for url in video_urls:
                video_results.append(
                    {
                        "url": url,
                        "status": "error",
                        "error": "SlowFast detector not available",
                        "is_ai_generated": None,
                        "ai_probability": None,
                        "confidence": 0.0,
                    }
                )
            return video_results, None, None

        for i, url in enumerate(video_urls):
            try:
                # First, check media registry for already processed video
                if media_registry.is_already_processed(post_id, url, "downloaded"):
                    # Use existing local file from registry
                    registry_record = media_registry.get_processed_media_info(post_id, url)
                    if registry_record and registry_record.local_path and registry_record.local_path.exists():
                        logger.info("Using already processed media for detection", 
                                  url=url[:50], local_path=str(registry_record.local_path))
                        video_file = registry_record.local_path
                    else:
                        logger.warning("Registry shows media processed but local file not found", 
                                     url=url[:50], local_path=str(registry_record.local_path) if registry_record else None)
                        # Fall through to database/fallback lookup
                        video_file = None
                else:
                    # Registry doesn't have this media, check database
                    media_record = media_info.get(url, {})
                    media_id = media_record.get("media_id")
                    storage_path = media_record.get("storage_path")
                    storage_type = media_record.get("storage_type")

                    # Handle different storage types
                    video_file = None
                    if storage_path:
                        if storage_type == "gcs":
                            # Download from GCS to local tmp directory for analysis
                            try:
                                from services.gcs_storage_service import GCSStorageService
                                from pathlib import Path
                                
                                gcs_service = GCSStorageService()
                                gcs_path = gcs_service.gcs_uri_to_path(storage_path)
                                
                                # Generate local path for downloaded file
                                local_path = self._get_local_file_path(post_id, url, "video")
                                local_path.parent.mkdir(parents=True, exist_ok=True)
                                
                                # Download from GCS and save locally
                                data = await gcs_service.download_media(gcs_path)
                                local_path.write_bytes(data)
                                
                                video_file = local_path
                                logger.info("Downloaded video from GCS for analysis", 
                                          url=url[:50], 
                                          gcs_path=gcs_path, 
                                          local_path=str(local_path))
                                          
                            except Exception as e:
                                logger.error("Failed to download video from GCS", 
                                           url=url[:50], 
                                           storage_path=storage_path, 
                                           error=str(e))
                                # Fall through to other fallback methods
                        else:
                            # Local storage
                            from pathlib import Path
                            video_file = Path(storage_path)
                    else:
                        # Fallback to finding file by URL hash if not in database
                        import hashlib

                        from core.config import settings

                        # Generate URL hash to match the downloaded file naming convention
                        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

                        # Construct the expected post media directory
                        post_media_dir = settings.tmp_dir / "posts" / post_id / "media"

                        # Find the video file with this URL hash in the post directory
                        video_file = None
                        if post_media_dir.exists():
                            for video_path in post_media_dir.glob(f"*{url_hash}*"):
                                if video_path.is_file() and video_path.suffix.lower() in [".mp4", ".avi", ".mov", ".webm"]:
                                    video_file = video_path
                                    break

                if not video_file or not video_file.exists():
                    logger.warning("Downloaded video file not found for analysis", url=url[:50])
                    
                    # Fallback: attempt to download if not already processed
                    if not media_registry.is_already_processed(post_id, url, "downloaded"):
                        logger.warning("Media not found in registry, downloading for detection", url=url[:50])
                        # This shouldn't happen in normal flow since FileUploadService should have processed it
                        
                    video_results.append(
                        {
                            "url": url,
                            "status": "error",
                            "error": "Downloaded video file not found",
                            "is_ai_generated": None,
                            "ai_probability": None,
                            "confidence": 0.0,
                        }
                    )
                    continue

                # Run real SlowFast detection on the downloaded video
                logger.debug("Running SlowFast detection", video_file=str(video_file))
                detection_result = detector.detect_video(str(video_file))

                # Convert SlowFast result format to our expected format
                is_ai_generated = detection_result.get("is_ai_generated", False)
                confidence = detection_result.get("confidence", 0.0)

                # Convert to probability (0.0 = human, 1.0 = AI)
                ai_probability = detection_result.get("ai_probability", 0.5)

                # Get media_id from database fallback if not found in first check
                media_id = None
                if not media_registry.is_already_processed(post_id, url, "downloaded"):
                    media_record = media_info.get(url, {})
                    media_id = media_record.get("media_id")

                # Update registry to mark as analyzed
                media_key = f"{post_id}:{url}"
                media_registry.update_processing_stage(media_key, "analyzed")

                result = {
                    "media_id": media_id,  # Include media ID from database
                    "url": url,
                    "status": "success",
                    "reason": "SlowFast AI detection on downloaded video",
                    "is_ai_generated": is_ai_generated,
                    "ai_probability": ai_probability,
                    "confidence": confidence,
                    "model_used": detection_result.get("model_used", "slowfast_r50"),
                    "processing_time": detection_result.get("processing_time"),
                    "local_file": str(video_file),
                    "error": None,
                }

                logger.info(
                    "SlowFast video analysis completed",
                    url=url,
                    local_file=str(video_file),
                    ai_probability=round(ai_probability, 3),
                    confidence=round(confidence, 3),
                    is_ai_generated=is_ai_generated,
                )
                video_results.append(result)

            except Exception as e:
                logger.error("Error analyzing video", url=url, error=str(e), exc_info=True)
                video_results.append(
                    {"url": url, "status": "error", "error": str(e), "is_ai_generated": None, "ai_probability": None, "confidence": 0.0}
                )

        # Calculate aggregate AI probability and confidence for all videos
        if video_results:
            successful_results = [r for r in video_results if r.get("status") == "success" and r.get("ai_probability") is not None]
            if successful_results:
                # Average the AI probabilities and confidences
                ai_probability = sum(r["ai_probability"] for r in successful_results) / len(successful_results)
                analysis_confidence = sum(r["confidence"] for r in successful_results) / len(successful_results)
                logger.info(
                    "Aggregate video analysis completed",
                    successful_videos=len(successful_results),
                    total_videos=len(video_results),
                    avg_ai_probability=round(ai_probability, 3),
                    avg_confidence=round(analysis_confidence, 3),
                )
            else:
                ai_probability = None
                analysis_confidence = None

        return video_results, ai_probability, analysis_confidence

    async def _update_post_with_media_analysis(
        self,
        post_id: str,
        image_ai_probability: Optional[float],
        image_confidence: Optional[float],
        video_ai_probability: Optional[float],
        video_confidence: Optional[float],
        db: AsyncSession,
    ) -> None:
        """Update the post in database with image and video analysis results."""
        from sqlalchemy import select

        from models import Post

        # Find the post that was created by text analysis
        result = await db.execute(select(Post).where(Post.post_id == post_id))
        post = result.scalar_one_or_none()

        if post:
            # Update the post with media analysis results
            post.image_ai_probability = image_ai_probability
            post.image_confidence = image_confidence
            post.video_ai_probability = video_ai_probability
            post.video_confidence = video_confidence

            await db.commit()
            logger.info(
                "Updated post with media analysis",
                post_id=post_id,
                image_ai_probability=image_ai_probability,
                image_confidence=image_confidence,
                video_ai_probability=video_ai_probability,
                video_confidence=video_confidence,
            )
        else:
            logger.warning("Post not found for media analysis update", post_id=post_id)

    def _create_aggregated_response(
        self,
        post_id: str,
        text_result,
        image_results: List[Dict[str, Any]],
        video_results: List[Dict[str, Any]],
        image_ai_probability: Optional[float] = None,
        image_confidence: Optional[float] = None,
        video_ai_probability: Optional[float] = None,
        video_confidence: Optional[float] = None,
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
            text_ai_probability=getattr(text_result, "text_ai_probability", None),
            text_confidence=getattr(text_result, "text_confidence", None),
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
                "from_cache": getattr(text_result, "debug_info", {}).get("from_cache", False),
            },
        )

    def _get_local_file_path(self, post_id: str, media_url: str, media_type: str):
        """
        Generate local file path for media storage (same as FileUploadService).

        Args:
            post_id: Facebook post ID
            media_url: Original media URL
            media_type: 'image' or 'video'

        Returns:
            Path object for local file storage
        """
        from core.config import settings
        import hashlib
        import uuid
        from pathlib import Path

        # Create post-specific folder: TMP_DIR/posts/{post_id}/media/
        post_folder = settings.tmp_dir / "posts" / post_id / "media"
        post_folder.mkdir(parents=True, exist_ok=True)

        # Generate unique filename based on URL hash and UUID
        url_hash = hashlib.md5(media_url.encode()).hexdigest()[:8]
        unique_id = str(uuid.uuid4())[:8]

        # Determine file extension from URL or use default
        extension = ".jpg" if media_type == "image" else ".mp4"
        if "." in media_url.split("/")[-1]:
            try:
                url_ext = "." + media_url.split(".")[-1].split("?")[0]
                if len(url_ext) <= 5:  # Reasonable extension length
                    extension = url_ext
            except (ValueError, IndexError):
                pass

        filename = f"{url_hash}_{unique_id}{extension}"
        return post_folder / filename
