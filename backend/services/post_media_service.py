"""Service for managing post media storage and Gemini uploads."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Post, PostMedia
from schemas.content_detection import ContentDetectionRequest, ContentDetectionResponse
from services.file_upload_service import FileUploadService
from utils.logging import get_logger

logger = get_logger(__name__)


class PostMediaService:
    """Service for managing post and media storage with Gemini upload integration."""

    def __init__(self):
        """Initialize the service with file upload capability."""
        try:
            self.file_service = FileUploadService()
            logger.info("PostMediaService initialized with Gemini file upload support")
        except Exception as e:
            logger.warning("FileUploadService initialization failed, media upload to Gemini disabled", error=str(e))
            self.file_service = None

    async def save_post_before_detection(
        self,
        request: ContentDetectionRequest,
        db: AsyncSession,
    ) -> Post:
        """
        Save post with its media to the database BEFORE detection processing.

        Args:
            request: Detection request with post content and media URLs
            db: Database session

        Returns:
            Created or updated Post object
        """
        # Check if post already exists
        result = await db.execute(select(Post).where(Post.post_id == request.post_id))
        existing_post = result.scalar_one_or_none()

        if existing_post:
            # Update existing post content
            existing_post.content = request.content
            existing_post.author = request.author
            existing_post.post_metadata = request.metadata
            post = existing_post
        else:
            # Create new post with placeholder values for detection results
            post = Post(
                post_id=request.post_id,
                content=request.content,
                author=request.author,
                verdict="pending",  # Will be updated after detection
                confidence=0.0,  # Will be updated after detection
                post_metadata=request.metadata,
            )
            db.add(post)

        await db.commit()
        await db.refresh(post)

        # Save media URLs if this is a new post or if media URLs have changed
        if not existing_post or await self._should_update_media(post.post_id, request, db):
            await self._save_media_urls(post.post_id, request, db)

        logger.info(
            "Post saved before detection",
            post_id=request.post_id,
            image_count=len(request.image_urls or []),
            video_count=len(request.video_urls or []),
            is_update=bool(existing_post),
        )

        return post

    async def update_post_with_results(
        self,
        post_id: str,
        response: ContentDetectionResponse,
        db: AsyncSession,
    ) -> Post:
        """
        Update post with detection results after processing.

        Args:
            post_id: Facebook post ID
            response: Detection response with analysis results
            db: Database session

        Returns:
            Updated Post object
        """
        # Get existing post
        result = await db.execute(select(Post).where(Post.post_id == post_id))
        post = result.scalar_one_or_none()

        if not post:
            raise ValueError(f"Post {post_id} not found")

        # Update with detection results
        post.verdict = response.verdict
        post.confidence = response.confidence
        post.explanation = response.explanation
        post.text_ai_probability = response.text_ai_probability
        post.text_confidence = response.text_confidence
        post.image_ai_probability = response.image_ai_probability
        post.image_confidence = response.image_confidence
        post.video_ai_probability = response.video_ai_probability
        post.video_confidence = response.video_confidence

        await db.commit()
        await db.refresh(post)

        logger.info(
            "Post updated with detection results",
            post_id=post_id,
            verdict=response.verdict,
            confidence=response.confidence,
        )

        return post

    async def _should_update_media(
        self,
        post_id: str,
        request: ContentDetectionRequest,
        db: AsyncSession,
    ) -> bool:
        """Check if media URLs have changed and need updating."""
        # Get existing media URLs
        result = await db.execute(select(PostMedia.media_url, PostMedia.media_type).where(PostMedia.post_id == post_id))
        existing_media = result.fetchall()

        existing_images = {url for url, media_type in existing_media if media_type == "image"}
        existing_videos = {url for url, media_type in existing_media if media_type == "video"}

        request_images = set(request.image_urls or [])
        request_videos = set(request.video_urls or [])

        # Return True if any media URLs have changed
        return existing_images != request_images or existing_videos != request_videos

    async def _save_media_urls(
        self,
        post_id: str,
        request: ContentDetectionRequest,
        db: AsyncSession,
    ) -> None:
        """Save media URLs to the post_media table and upload to Gemini."""
        # Delete existing media for this post
        await db.execute(PostMedia.__table__.delete().where(PostMedia.post_id == post_id))

        # Upload media to Gemini first (if service available)
        gemini_file_uris = []
        media_file_info = []
        if self.file_service and (request.image_urls or request.video_urls):
            try:
                logger.info(
                    "Uploading media to Gemini during post processing",
                    post_id=post_id,
                    image_count=len(request.image_urls or []),
                    video_count=len(request.video_urls or []),
                )
                gemini_file_uris, media_file_info = await self.file_service.upload_media_from_urls(
                    request.image_urls or [], request.video_urls or [], post_id=post_id, db=db
                )
                logger.info(
                    "Gemini upload completed",
                    post_id=post_id,
                    successful_uploads=len(gemini_file_uris),
                    total_media=len((request.image_urls or []) + (request.video_urls or [])),
                )
            except Exception as e:
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in ["signature", "expired", "invalid", "forbidden", "403"]):
                    logger.warning(
                        "Media upload failed due to expired/invalid URLs",
                        post_id=post_id,
                        error=str(e),
                        suggestion="Facebook URLs may have expired - this is normal for older posts",
                    )
                else:
                    logger.error("Failed to upload media to Gemini during post processing", post_id=post_id, error=str(e))
                # Continue with database storage even if Gemini upload fails

        media_entries = []
        gemini_uri_index = 0
        
        # Create lookup dictionary for local file paths
        local_file_lookup = {}
        for file_info in media_file_info:
            local_file_lookup[file_info["url"]] = file_info.get("local_path")

        # Add image URLs
        for image_url in request.image_urls or []:
            gemini_uri = gemini_file_uris[gemini_uri_index] if gemini_uri_index < len(gemini_file_uris) else None
            local_path = local_file_lookup.get(image_url)
            media_entry = PostMedia(
                id=str(uuid.uuid4()),
                post_id=post_id,
                media_type="image",
                media_url=image_url,
                gemini_file_uri=gemini_uri,
                local_file_path=local_path,
            )
            media_entries.append(media_entry)
            gemini_uri_index += 1

        # Add video URLs
        for video_url in request.video_urls or []:
            gemini_uri = gemini_file_uris[gemini_uri_index] if gemini_uri_index < len(gemini_file_uris) else None
            local_path = local_file_lookup.get(video_url)
            media_entry = PostMedia(
                id=str(uuid.uuid4()),
                post_id=post_id,
                media_type="video",
                media_url=video_url,
                gemini_file_uri=gemini_uri,
                local_file_path=local_path,
            )
            media_entries.append(media_entry)
            gemini_uri_index += 1

        # Bulk insert media entries
        if media_entries:
            db.add_all(media_entries)
            await db.commit()

            successful_gemini_uploads = sum(1 for entry in media_entries if entry.gemini_file_uri)
            logger.info(
                "Media URLs saved with Gemini integration",
                post_id=post_id,
                image_count=len(request.image_urls or []),
                video_count=len(request.video_urls or []),
                total_media=len(media_entries),
                gemini_uploads=successful_gemini_uploads,
            )
