import asyncio
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
            from db.models import PostMedia

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
                    # Only local storage is supported
                    from pathlib import Path

                    local_path = Path(media.storage_path) if media.storage_path else None
                    if local_path and local_path.exists():
                        mime_type = self._get_mime_type_from_media_type(media.media_type)
                        display_name = f"{media.media_type}_{media.post_id}_{media.id}"

                        gemini_uri = await self._upload_to_gemini_from_storage(str(local_path), mime_type, display_name)

                        if gemini_uri:
                            media.gemini_file_uri = gemini_uri
                            recovered_uris[media.media_url] = gemini_uri

                            logger.info(
                                "Successfully recovered Gemini URI",
                                post_id=post_id,
                                media_url=media.media_url[:50],
                                storage_path=str(local_path),
                                gemini_uri=gemini_uri,
                            )
                    else:
                        logger.warning(
                            "Local storage file missing, cannot recover Gemini URI", post_id=post_id, storage_path=media.storage_path
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

    async def _upload_to_gemini_from_storage(self, storage_path: str, mime_type: str, display_name: str) -> Optional[str]:
        """Upload file from local storage to Gemini without blocking the event loop."""
        try:
            # Upload to Gemini File API directly from the provided local path (run in thread)
            file = await asyncio.to_thread(
                genai.upload_file,
                path=storage_path,
                mime_type=mime_type,
                display_name=display_name,
            )

            # Wait for processing with non-blocking sleeps
            max_retries = 60 if mime_type.startswith("video/") else 10
            sleep_seconds = 2 if mime_type.startswith("video/") else 1
            for _ in range(max_retries):
                file = await asyncio.to_thread(genai.get_file, file.name)
                state = getattr(file, "state", None)
                state_name = getattr(state, "name", "") if state else ""
                if state_name == "ACTIVE":
                    return file.uri
                elif state_name == "FAILED":
                    logger.error("Gemini file processing failed", file_name=file.name)
                    return None

                await asyncio.sleep(sleep_seconds)

            logger.warning("Gemini file processing timeout", file_name=file.name)
            return None

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
