import time
from typing import Dict, Optional

import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class GeminiRecoveryService:
    """Service for recovering lost Gemini URIs and managing uploads efficiently."""

    def __init__(self):
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)

    async def recover_missing_gemini_uris(self, post_id: str, db: AsyncSession) -> Dict[str, str]:
        """
        Recover missing Gemini URIs by uploading existing storage files.

        Returns:
            Dict mapping media_url -> recovered_gemini_uri
        """
        try:
            from models import PostMedia
            from services.gcs_storage_service import GCSStorageService

            gcs_service = GCSStorageService()

            # Find media with storage but missing Gemini URIs
            missing_gemini_result = await db.execute(
                select(PostMedia)
                .where(PostMedia.post_id == post_id)
                .where(PostMedia.storage_path.isnot(None))
                .where(PostMedia.gemini_file_uri.is_(None))
            )
            media_missing_gemini = missing_gemini_result.scalars().all()

            if not media_missing_gemini:
                return {}

            logger.info(
                "Found media with missing Gemini URIs, attempting recovery", post_id=post_id, missing_count=len(media_missing_gemini)
            )

            recovered_uris = {}

            for media in media_missing_gemini:
                try:
                    # Check if file still exists in storage
                    if media.storage_path.startswith("gs://"):
                        gcs_path = gcs_service.gcs_uri_to_path(media.storage_path)

                        if await gcs_service.media_exists(gcs_path):
                            # File exists in storage, upload to Gemini
                            mime_type = self._get_mime_type_from_media_type(media.media_type)
                            display_name = f"{media.media_type}_{media.post_id}_{media.id}"

                            gemini_uri = await self._upload_to_gemini_from_storage(media.storage_path, mime_type, display_name, gcs_service)

                            if gemini_uri:
                                # Update database with recovered URI
                                media.gemini_file_uri = gemini_uri
                                recovered_uris[media.media_url] = gemini_uri

                                logger.info(
                                    "Successfully recovered Gemini URI",
                                    post_id=post_id,
                                    media_url=media.media_url[:50],
                                    storage_path=media.storage_path,
                                    gemini_uri=gemini_uri,
                                )
                        else:
                            logger.warning(
                                "Storage file missing, cannot recover Gemini URI", post_id=post_id, storage_path=media.storage_path
                            )

                except Exception as e:
                    logger.error("Failed to recover Gemini URI for media", post_id=post_id, media_id=media.id, error=str(e))

            # Commit all recovered URIs
            if recovered_uris:
                await db.commit()
                logger.info(
                    "Gemini URI recovery completed",
                    post_id=post_id,
                    recovered_count=len(recovered_uris),
                    total_missing=len(media_missing_gemini),
                )

            return recovered_uris

        except Exception as e:
            logger.error("Error in Gemini URI recovery", post_id=post_id, error=str(e))
            return {}

    async def _upload_to_gemini_from_storage(self, storage_path: str, mime_type: str, display_name: str, gcs_service) -> Optional[str]:
        """Upload file from GCS storage to Gemini (optimized version)."""
        try:
            import os
            import tempfile

            # Download from GCS to temporary file
            gcs_path = gcs_service.gcs_uri_to_path(storage_path)
            data = await gcs_service.download_media(gcs_path)

            # Get appropriate file extension
            extension_map = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "video/mp4": ".mp4",
                "video/webm": ".webm",
            }
            extension = extension_map.get(mime_type, ".tmp")

            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
                temp_file.write(data)
                temp_file_path = temp_file.name

            try:
                # Upload to Gemini File API
                file = genai.upload_file(path=temp_file_path, mime_type=mime_type, display_name=display_name)

                # Wait for processing
                max_retries = 60 if mime_type.startswith("video/") else 10
                for attempt in range(max_retries):
                    file = genai.get_file(file.name)
                    if file.state.name == "ACTIVE":
                        return file.uri
                    elif file.state.name == "FAILED":
                        logger.error("Gemini file processing failed", file_name=file.name)
                        return None

                    time.sleep(2 if mime_type.startswith("video/") else 1)

                logger.warning("Gemini file processing timeout", file_name=file.name)
                return None

            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)

        except Exception as e:
            logger.error("Failed to upload to Gemini from storage", storage_path=storage_path, error=str(e))
            return None

    def _get_mime_type_from_media_type(self, media_type: str) -> str:
        """Convert media type to MIME type."""
        type_mapping = {"image": "image/jpeg", "video": "video/mp4"}
        return type_mapping.get(media_type, "application/octet-stream")

    async def check_and_recover_all_missing_uris(self, post_id: str, db: AsyncSession) -> int:
        """
        Check for and recover all missing Gemini URIs for a post.

        Returns:
            Number of URIs recovered
        """
        recovered_uris = await self.recover_missing_gemini_uris(post_id, db)
        return len(recovered_uris)


# Global instance
gemini_recovery_service = GeminiRecoveryService()
