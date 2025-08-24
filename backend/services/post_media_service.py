"""Service for managing post media storage and Gemini uploads."""

from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from models import Post, PostMedia
from schemas.content_detection import ContentDetectionRequest, ContentDetectionResponse
from services.file_upload_service import FileUploadService
from utils.logging import get_logger
from utils.media_id_extractor import generate_composite_media_id

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

        # Always check for media changes with the new smart diffing approach
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

    async def _detect_media_changes(
        self, 
        post_id: str, 
        new_image_urls: List[str], 
        new_video_urls: List[str], 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Detect what media URLs have actually changed.
        
        Returns:
            {
                'unchanged_media': List[PostMedia],  # Keep these as-is
                'urls_to_remove': List[str],         # Delete these
                'urls_to_add': List[str],           # Add these
                'needs_update': bool                # Whether any changes detected
            }
        """
        try:
            # Get existing media URLs
            existing_result = await db.execute(
                select(PostMedia)
                .where(PostMedia.post_id == post_id)
            )
            existing_media = existing_result.scalars().all()
            
            # Separate existing URLs by type
            existing_image_urls = {
                media.media_url for media in existing_media 
                if media.media_type == "image"
            }
            existing_video_urls = {
                media.media_url for media in existing_media 
                if media.media_type == "video"
            }
            
            # Convert new URLs to sets
            new_image_set = set(new_image_urls or [])
            new_video_set = set(new_video_urls or [])
            
            # Find differences
            all_existing_urls = existing_image_urls | existing_video_urls
            all_new_urls = new_image_set | new_video_set
            
            urls_to_remove = all_existing_urls - all_new_urls
            urls_to_add = all_new_urls - all_existing_urls
            unchanged_urls = all_existing_urls & all_new_urls
            
            # Get unchanged media objects to preserve
            unchanged_media = [
                media for media in existing_media 
                if media.media_url in unchanged_urls
            ]
            
            needs_update = bool(urls_to_remove or urls_to_add)
            
            logger.info(
                "Media change detection completed",
                post_id=post_id,
                total_existing=len(all_existing_urls),
                total_new=len(all_new_urls),
                unchanged=len(unchanged_urls),
                to_remove=len(urls_to_remove),
                to_add=len(urls_to_add),
                needs_update=needs_update
            )
            
            return {
                'unchanged_media': unchanged_media,
                'urls_to_remove': list(urls_to_remove),
                'urls_to_add': list(urls_to_add),
                'needs_update': needs_update
            }
        
        except Exception as e:
            logger.error("Error detecting media changes", post_id=post_id, error=str(e))
            # Fallback to full update if detection fails
            return {
                'unchanged_media': [],
                'urls_to_remove': [],
                'urls_to_add': new_image_urls + new_video_urls,
                'needs_update': True
            }


    async def _create_media_entries_for_new_urls(
        self,
        post_id: str,
        image_urls: List[str],
        video_urls: List[str],
        gemini_file_uris: List[str],
        media_file_info: List[dict],
        db: AsyncSession
    ) -> None:
        """Create PostMedia entries only for new URLs using upsert."""
        
        media_data = []
        gemini_uri_index = 0
        
        # Create lookup dictionary for storage paths
        storage_path_lookup = {}
        for file_info in media_file_info:
            storage_path_lookup[file_info["url"]] = file_info.get("storage_path")
        
        # Process new image URLs
        for image_url in image_urls:
            gemini_uri = gemini_file_uris[gemini_uri_index] if gemini_uri_index < len(gemini_file_uris) else None
            storage_path = storage_path_lookup.get(image_url)
            
            media_id = generate_composite_media_id(post_id, image_url, "image")
            storage_type = None
            if storage_path:
                storage_type = "gcs" if storage_path.startswith("gs://") else "local"
            
            media_data.append({
                "id": media_id,
                "post_id": post_id,
                "media_type": "image",
                "media_url": image_url,
                "gemini_file_uri": gemini_uri,
                "storage_path": storage_path,
                "storage_type": storage_type,
            })
            gemini_uri_index += 1
        
        # Process new video URLs
        for video_url in video_urls:
            gemini_uri = gemini_file_uris[gemini_uri_index] if gemini_uri_index < len(gemini_file_uris) else None
            storage_path = storage_path_lookup.get(video_url)
            
            media_id = generate_composite_media_id(post_id, video_url, "video")
            storage_type = None
            if storage_path:
                storage_type = "gcs" if storage_path.startswith("gs://") else "local"
            
            media_data.append({
                "id": media_id,
                "post_id": post_id,
                "media_type": "video",
                "media_url": video_url,
                "gemini_file_uri": gemini_uri,
                "storage_path": storage_path,
                "storage_type": storage_type,
            })
            gemini_uri_index += 1
        
        # Use upsert to insert new entries
        if media_data:
            stmt = insert(PostMedia).values(media_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "media_url": stmt.excluded.media_url,
                    "gemini_file_uri": stmt.excluded.gemini_file_uri,
                    "storage_path": stmt.excluded.storage_path,
                    "storage_type": stmt.excluded.storage_type,
                    "updated_at": stmt.excluded.updated_at,
                }
            )
            await db.execute(stmt)
            await db.commit()

    async def _save_media_urls(
        self,
        post_id: str,
        request: ContentDetectionRequest,
        db: AsyncSession,
    ) -> None:
        """Optimized media URL saving with smart diffing."""
        
        # Step 1: Detect what actually changed
        changes = await self._detect_media_changes(
            post_id, 
            request.image_urls or [], 
            request.video_urls or [], 
            db
        )
        
        # Step 2: Skip processing if nothing changed
        if not changes['needs_update']:
            logger.info("No media changes detected, skipping media processing", post_id=post_id)
            return
        
        # Step 3: Remove only URLs that are no longer needed
        if changes['urls_to_remove']:
            await db.execute(
                PostMedia.__table__.delete()
                .where(PostMedia.post_id == post_id)
                .where(PostMedia.media_url.in_(changes['urls_to_remove']))
            )
            logger.info(
                "Removed obsolete media records",
                post_id=post_id,
                removed_count=len(changes['urls_to_remove'])
            )
        
        # Step 4: Process only new URLs
        if changes['urls_to_add']:
            new_image_urls = [url for url in (request.image_urls or []) if url in changes['urls_to_add']]
            new_video_urls = [url for url in (request.video_urls or []) if url in changes['urls_to_add']]
            
            # Upload only new media to Gemini
            gemini_file_uris = []
            media_file_info = []
            if self.file_service and (new_image_urls or new_video_urls):
                try:
                    logger.info(
                        "Processing only new media URLs",
                        post_id=post_id,
                        new_images=len(new_image_urls),
                        new_videos=len(new_video_urls),
                        unchanged_preserved=len(changes['unchanged_media'])
                    )
                    
                    gemini_file_uris, media_file_info = await self.file_service.upload_media_from_urls(
                        new_image_urls, new_video_urls, post_id=post_id, db=db
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
                        logger.error("Failed to process new media URLs", post_id=post_id, error=str(e))
            
            # Step 5: Create media entries only for new URLs
            await self._create_media_entries_for_new_urls(
                post_id, new_image_urls, new_video_urls, 
                gemini_file_uris, media_file_info, db
            )
        
        logger.info(
            "Smart media update completed",
            post_id=post_id,
            preserved_records=len(changes['unchanged_media']),
            added_records=len(changes['urls_to_add']),
            removed_records=len(changes['urls_to_remove'])
        )
