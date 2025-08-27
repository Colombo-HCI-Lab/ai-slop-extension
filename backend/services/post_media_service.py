"""Service for managing post media storage and Gemini uploads (unified pipeline)."""

from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from db.models import Post
from schemas.content_detection import ContentDetectionRequest, ContentDetectionResponse
from services.media_pipeline import MediaPipeline, MediaItem
from utils.logging import get_logger


logger = get_logger(__name__)


class PostMediaService:
    """Service for managing post and media storage with Gemini upload integration."""

    def __init__(self):
        """Initialize the service with unified media pipeline."""
        self.pipeline = MediaPipeline()

    async def save_post_before_detection(
        self,
        request: ContentDetectionRequest,
        db: AsyncSession,
    ) -> Post:
        """
        Save post with its media to the database BEFORE detection processing.
        Uses upsert to handle concurrent requests safely.

        Args:
            request: Detection request with post content and media URLs
            db: Database session

        Returns:
            Created or updated Post object
        """
        # Use upsert to handle race conditions
        stmt = insert(Post).values(
            post_id=request.post_id,
            content=request.content,
            author=request.author,
            verdict="pending",
            confidence=0.0,
            post_metadata=request.metadata,
        )

        # On conflict, update the existing record
        stmt = stmt.on_conflict_do_update(
            index_elements=["post_id"],
            set_=dict(
                content=stmt.excluded.content,
                author=stmt.excluded.author,
                post_metadata=stmt.excluded.post_metadata,
                updated_at=stmt.excluded.updated_at,
            ),
        )

        await db.execute(stmt)
        await db.commit()

        # Fetch the post to return
        result = await db.execute(select(Post).where(Post.post_id == request.post_id))
        post = result.scalar_one()

        # Unified pipeline: remove obsolete media rows then process provided media
        incoming_urls = set((request.image_urls or []) + (request.video_urls or []))

        # Always process media if we have URLs or if post has videos
        if incoming_urls or request.has_videos:
            from services.media_repo import MediaRepo

            repo = MediaRepo()

            items = [MediaItem(url=u, media_type="image") for u in (request.image_urls or [])]
            video_urls = list(request.video_urls or [])

            # Use yt-dlp when post has videos but no direct video URLs
            if request.has_videos and request.post_url and not video_urls:
                video_urls.append(f"yt-dlp://{post.post_id}")

            items += [MediaItem(url=u, media_type="video") for u in video_urls]

            # Update URLs for cleanup - include yt-dlp URLs
            all_urls = set((request.image_urls or []) + video_urls)
            await repo.delete_missing(post_id=post.post_id, valid_urls=all_urls, db=db)

            await self.pipeline.process_media(post_id=post.post_id, items=items, db=db, context={"post_url": request.post_url})

        # Count final video URLs after processing
        final_video_count = 0
        yt_dlp_created = False
        if incoming_urls or request.has_videos:
            video_urls_for_logging = list(request.video_urls or [])
            if request.has_videos and request.post_url and not video_urls_for_logging:
                video_urls_for_logging.append(f"yt-dlp://{request.post_id}")
                yt_dlp_created = True
            final_video_count = len(video_urls_for_logging)

        logger.info(
            "Post saved before detection",
            post_id=request.post_id,
            image_count=len(request.image_urls or []),
            video_count=final_video_count,
            has_videos=request.has_videos,
            created_yt_dlp_url=yt_dlp_created,
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

    # Legacy media helpers removed in unified pipeline
