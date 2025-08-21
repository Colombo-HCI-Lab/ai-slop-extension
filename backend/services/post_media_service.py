"""Service for managing post media storage."""

import uuid
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import Post, PostMedia
from schemas.content_detection import ContentDetectionRequest, ContentDetectionResponse
from utils.logging import get_logger

logger = get_logger(__name__)


class PostMediaService:
    """Service for managing post and media storage."""

    async def save_post_with_media(
        self,
        request: ContentDetectionRequest,
        response: ContentDetectionResponse,
        db: AsyncSession,
    ) -> Post:
        """
        Save post with its media to the database.

        Args:
            request: Original detection request with media URLs
            response: Detection response with analysis results
            db: Database session

        Returns:
            Created or updated Post object
        """
        # Check if post already exists
        result = await db.execute(select(Post).where(Post.post_id == request.post_id))
        existing_post = result.scalar_one_or_none()

        if existing_post:
            # Update existing post with new analysis results
            existing_post.content = request.content
            existing_post.author = request.author
            existing_post.verdict = response.verdict
            existing_post.confidence = response.confidence
            existing_post.explanation = response.explanation
            existing_post.text_ai_probability = response.text_ai_probability
            existing_post.text_confidence = response.text_confidence
            existing_post.image_ai_probability = response.image_ai_probability
            existing_post.image_confidence = response.image_confidence
            existing_post.video_ai_probability = response.video_ai_probability
            existing_post.video_confidence = response.video_confidence
            existing_post.post_metadata = request.metadata

            post = existing_post
        else:
            # Create new post
            post = Post(
                id=str(uuid.uuid4()),
                post_id=request.post_id,
                content=request.content,
                author=request.author,
                verdict=response.verdict,
                confidence=response.confidence,
                explanation=response.explanation,
                text_ai_probability=response.text_ai_probability,
                text_confidence=response.text_confidence,
                image_ai_probability=response.image_ai_probability,
                image_confidence=response.image_confidence,
                video_ai_probability=response.video_ai_probability,
                video_confidence=response.video_confidence,
                post_metadata=request.metadata,
            )
            db.add(post)

        await db.commit()
        await db.refresh(post)

        # Save media URLs if this is a new post or if media URLs have changed
        if not existing_post or await self._should_update_media(post.id, request, db):
            await self._save_media_urls(post.id, request, db)

        logger.info(
            "Post saved with media",
            post_id=request.post_id,
            post_db_id=post.id,
            image_count=len(request.image_urls or []),
            video_count=len(request.video_urls or []),
            is_update=bool(existing_post),
        )

        return post

    async def _should_update_media(
        self,
        post_db_id: str,
        request: ContentDetectionRequest,
        db: AsyncSession,
    ) -> bool:
        """Check if media URLs have changed and need updating."""
        # Get existing media URLs
        result = await db.execute(select(PostMedia.media_url, PostMedia.media_type).where(PostMedia.post_db_id == post_db_id))
        existing_media = result.fetchall()

        existing_images = {url for url, media_type in existing_media if media_type == "image"}
        existing_videos = {url for url, media_type in existing_media if media_type == "video"}

        request_images = set(request.image_urls or [])
        request_videos = set(request.video_urls or [])

        # Return True if any media URLs have changed
        return existing_images != request_images or existing_videos != request_videos

    async def _save_media_urls(
        self,
        post_db_id: str,
        request: ContentDetectionRequest,
        db: AsyncSession,
    ) -> None:
        """Save media URLs to the post_media table."""
        # Delete existing media for this post
        await db.execute(PostMedia.__table__.delete().where(PostMedia.post_db_id == post_db_id))

        media_entries = []

        # Add image URLs
        for image_url in request.image_urls or []:
            media_entry = PostMedia(
                id=str(uuid.uuid4()),
                post_db_id=post_db_id,
                media_type="image",
                media_url=image_url,
            )
            media_entries.append(media_entry)

        # Add video URLs
        for video_url in request.video_urls or []:
            media_entry = PostMedia(
                id=str(uuid.uuid4()),
                post_db_id=post_db_id,
                media_type="video",
                media_url=video_url,
            )
            media_entries.append(media_entry)

        # Bulk insert media entries
        if media_entries:
            db.add_all(media_entries)
            await db.commit()

            logger.info(
                "Media URLs saved",
                post_db_id=post_db_id,
                image_count=len(request.image_urls or []),
                video_count=len(request.video_urls or []),
                total_media=len(media_entries),
            )
