import hashlib
import aiohttp
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from utils.logging import get_logger

logger = get_logger(__name__)


class ContentDeduplicationService:
    """Service for detecting and handling duplicate media content."""

    def __init__(self):
        self.hash_cache: Dict[str, str] = {}  # URL -> content_hash
        self.content_registry: Dict[str, Dict] = {}  # content_hash -> metadata

    async def calculate_content_hash(self, data: bytes) -> str:
        """Calculate SHA-256 hash of media content."""
        return hashlib.sha256(data).hexdigest()

    async def get_url_content_hash(self, url: str, data: Optional[bytes] = None) -> Optional[str]:
        """Get content hash for a URL (with caching)."""

        # Check cache first
        if url in self.hash_cache:
            return self.hash_cache[url]

        try:
            if data is None:
                # Download just enough data to calculate hash
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.read()
                        else:
                            return None

            content_hash = await self.calculate_content_hash(data)

            # Cache the result
            self.hash_cache[url] = content_hash

            return content_hash

        except Exception as e:
            logger.error("Failed to calculate content hash", url=url, error=str(e))
            return None

    def normalize_facebook_url(self, url: str) -> str:
        """Normalize Facebook URL by removing session parameters."""
        try:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)

            # Remove Facebook session parameters
            params_to_remove = ["_nc_sid", "_nc_ohc", "_nc_ht", "_nc_cat", "ccb", "efg", "_nc_eui2", "oh", "oe"]

            for param in params_to_remove:
                query_params.pop(param, None)

            # Reconstruct URL without session params
            clean_query = urlencode(query_params, doseq=True)
            normalized_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, parsed.fragment))

            return normalized_url

        except Exception as e:
            logger.warning("Failed to normalize Facebook URL", url=url, error=str(e))
            return url

    async def find_duplicate_content(self, post_id: str, new_urls: List[str], db: AsyncSession) -> Dict[str, str]:
        """
        Find existing media with identical content.

        Returns:
            Dict mapping new_url -> existing_storage_path (for duplicates)
        """
        try:
            from db.models import PostMedia

            # Get all existing media for this post
            existing_result = await db.execute(
                select(PostMedia.media_url, PostMedia.storage_path, PostMedia.content_hash)
                .where(PostMedia.post_id == post_id)
                .where(PostMedia.content_hash.isnot(None))
            )
            existing_media = existing_result.fetchall()

            # Build hash -> storage_path mapping
            hash_to_storage = {}
            for media_url, storage_path, content_hash in existing_media:
                if content_hash and storage_path:
                    hash_to_storage[content_hash] = storage_path

            duplicates = {}

            # Check each new URL for duplicates
            for new_url in new_urls:
                try:
                    # Try URL normalization first (fast check)
                    normalized_url = self.normalize_facebook_url(new_url)

                    # Check if we've seen this normalized URL before
                    for existing_url, storage_path, _ in existing_media:
                        if self.normalize_facebook_url(existing_url) == normalized_url:
                            duplicates[new_url] = storage_path
                            logger.info("Found duplicate via URL normalization", new_url=new_url, existing_url=existing_url)
                            break
                    else:
                        # If URL normalization didn't work, try content hashing
                        # (This requires downloading, so only do if necessary)
                        content_hash = await self.get_url_content_hash(new_url)

                        if content_hash and content_hash in hash_to_storage:
                            duplicates[new_url] = hash_to_storage[content_hash]
                            logger.info("Found duplicate via content hash", new_url=new_url, content_hash=content_hash[:16])

                except Exception as e:
                    logger.error("Error checking for duplicate", url=new_url, error=str(e))

            if duplicates:
                logger.info(
                    "Content deduplication completed",
                    post_id=post_id,
                    new_urls_count=len(new_urls),
                    duplicates_found=len(duplicates),
                    bandwidth_saved="estimated",
                )

            return duplicates

        except Exception as e:
            logger.error("Error in duplicate detection", post_id=post_id, error=str(e))
            return {}


# Global instance
deduplication_service = ContentDeduplicationService()
