from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.gemini_recovery_service import gemini_recovery_service
from utils.logging import get_logger

logger = get_logger(__name__)


class GeminiOnDemandService:
    """Service for uploading media to Gemini only when actually needed."""

    async def ensure_gemini_uri_exists(self, post_id: str, media_url: str, db: AsyncSession) -> Optional[str]:
        """
        Ensure a Gemini URI exists for the given media, uploading if necessary.

        This is called when:
        1. User starts a chat about the post
        2. Detection analysis needs the media
        3. Any other operation requires Gemini access
        """
        try:
            from db.models import PostMedia

            # Check if Gemini URI already exists
            result = await db.execute(
                select(PostMedia.gemini_file_uri, PostMedia.storage_path, PostMedia.media_type)
                .where(PostMedia.post_id == post_id)
                .where(PostMedia.media_url == media_url)
            )
            row = result.first()

            if not row:
                logger.warning("Media not found in database", post_id=post_id, media_url=media_url)
                return None

            gemini_uri, storage_path, media_type = row

            # If Gemini URI already exists, return it
            if gemini_uri:
                logger.info("Gemini URI already exists", post_id=post_id, uri=gemini_uri)
                return gemini_uri

            # If no Gemini URI but storage exists, upload from storage
            if storage_path:
                logger.info("Uploading to Gemini on-demand", post_id=post_id, storage_path=storage_path)

                mime_type = self._get_mime_type_from_media_type(media_type)
                display_name = f"{media_type}_{post_id}_{hash(media_url) % 10000}"

                gemini_uri = await gemini_recovery_service._upload_to_gemini_from_storage(storage_path, mime_type, display_name)

                if gemini_uri:
                    # Update database with new Gemini URI
                    await db.execute(
                        PostMedia.__table__.update()
                        .where(PostMedia.post_id == post_id)
                        .where(PostMedia.media_url == media_url)
                        .values(gemini_file_uri=gemini_uri)
                    )
                    await db.commit()

                    logger.info("On-demand Gemini upload successful", post_id=post_id, gemini_uri=gemini_uri)

                return gemini_uri

            logger.warning("No storage path available for on-demand upload", post_id=post_id, media_url=media_url)
            return None

        except Exception as e:
            logger.error("Error in on-demand Gemini upload", post_id=post_id, media_url=media_url, error=str(e))
            return None

    async def batch_ensure_gemini_uris(self, post_id: str, media_urls: List[str], db: AsyncSession) -> List[str]:
        """Ensure Gemini URIs exist for multiple media files."""

        uris = []
        for url in media_urls:
            uri = await self.ensure_gemini_uri_exists(post_id, url, db)
            if uri:
                uris.append(uri)

        logger.info("Batch on-demand Gemini upload completed", post_id=post_id, requested_count=len(media_urls), successful_count=len(uris))

        return uris

    def _get_mime_type_from_media_type(self, media_type: str) -> str:
        """Convert media type to MIME type."""
        type_mapping = {"image": "image/jpeg", "video": "video/mp4"}
        return type_mapping.get(media_type, "application/octet-stream")


# Global instance
gemini_on_demand_service = GeminiOnDemandService()
