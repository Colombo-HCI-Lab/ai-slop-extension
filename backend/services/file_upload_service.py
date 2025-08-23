"""File upload service for handling image and video uploads to Gemini File API."""

import io
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

import aiohttp
import google.generativeai as genai
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class FileUploadService:
    """Handles image and video uploads to Gemini File API."""

    def __init__(self):
        """Initialize the file upload service."""
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for file upload functionality")

        # Configure Gemini API
        genai.configure(api_key=settings.gemini_api_key)

    def _get_local_file_path(self, post_id: str, media_url: str, media_type: str) -> Path:
        """
        Generate local file path for media storage.

        Args:
            post_id: Facebook post ID
            media_url: Original media URL
            media_type: 'image' or 'video'

        Returns:
            Path object for local file storage
        """
        # Create post-specific folder: TMP_DIR/posts/{post_id}/media/
        post_folder = settings.tmp_dir / "posts" / post_id / "media"
        post_folder.mkdir(parents=True, exist_ok=True)

        # Generate unique filename based on URL hash and UUID
        import hashlib

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

    async def check_local_file_exists(self, post_id: str, media_url: str, db: AsyncSession) -> Optional[str]:
        """
        Check if media file already exists locally.

        Args:
            post_id: Facebook post ID
            media_url: Original media URL
            db: Database session

        Returns:
            Local file path if exists, None otherwise
        """
        try:
            from models import PostMedia

            # Check database for existing local file path
            media_result = await db.execute(
                select(PostMedia.local_file_path)
                .where(PostMedia.post_id == post_id)
                .where(PostMedia.media_url == media_url)
                .where(PostMedia.local_file_path.isnot(None))
            )
            local_path = media_result.scalar_one_or_none()

            if local_path and Path(local_path).exists():
                logger.info(
                    "Local file already exists, skipping download",
                    post_id=post_id,
                    media_url=media_url[:100] + "..." if len(media_url) > 100 else media_url,
                    local_path=local_path,
                )
                return local_path

            return None

        except Exception as e:
            logger.error(
                "Error checking for existing local file",
                post_id=post_id,
                media_url=media_url[:100] + "..." if len(media_url) > 100 else media_url,
                error=str(e),
            )
            return None

    async def _upload_to_gemini_from_file(self, file_path: str, mime_type: str, display_name: str) -> Optional[str]:
        """
        Upload existing local file to Gemini File API.

        Args:
            file_path: Path to local file
            mime_type: MIME type of the file
            display_name: Display name for the file

        Returns:
            Gemini file URI or None if failed
        """
        try:
            # Upload to Gemini File API
            file = genai.upload_file(path=file_path, mime_type=mime_type, display_name=display_name)

            # Wait for file to be processed
            import time

            max_retries = 60 if mime_type.startswith("video/") else 10
            for attempt in range(max_retries):
                file = genai.get_file(file.name)
                if file.state.name == "ACTIVE":
                    return file.uri
                elif file.state.name == "FAILED":
                    logger.error("Gemini file processing failed", file_name=file.name)
                    return None

                # Log progress for longer processing
                if mime_type.startswith("video/") and attempt % 10 == 0:
                    logger.info(f"File still processing... ({attempt + 1}/{max_retries})", file_name=file.name, state=file.state.name)

                # Wait before checking again
                time.sleep(2 if mime_type.startswith("video/") else 1)

            logger.warning("Gemini file processing timeout", file_name=file.name)
            return None

        except Exception as e:
            logger.error("Failed to upload local file to Gemini", file_path=file_path, error=str(e), exc_info=True)
            return None

    def check_post_media_directory_exists(self, post_id: str) -> bool:
        """
        Check if the post directory already exists.
        If it exists with the media subfolder, assume all media has been downloaded and uploaded.

        Facebook image URLs change on each page load, but post_id remains constant.
        Therefore, folder existence = post fully processed.

        Args:
            post_id: Facebook post ID

        Returns:
            True if post directory exists (indicating post was processed), False otherwise
        """
        try:
            # Check for the post directory structure: TMP_DIR/posts/{post_id}/
            post_dir = settings.tmp_dir / "posts" / post_id
            post_media_dir = post_dir / "media"

            # If the post directory structure exists, consider it processed
            if post_dir.exists() and post_media_dir.exists():
                # Count files to ensure it's not just an empty structure
                files = list(post_media_dir.glob("*"))
                if files:
                    logger.info(
                        "Post directory exists with media files - post already processed",
                        post_id=post_id,
                        directory=str(post_media_dir),
                        file_count=len(files),
                        status="fully_processed",
                    )
                    return True
                else:
                    logger.debug(
                        "Post directory exists but media folder is empty",
                        post_id=post_id,
                        directory=str(post_media_dir),
                        status="incomplete",
                    )

            return False

        except Exception as e:
            logger.error("Error checking post directory", post_id=post_id, error=str(e))
            return False

    async def check_post_exists_in_database(self, post_id: str, db: AsyncSession) -> bool:
        """
        Check if a post record exists in the database WITH completed detection.
        Only posts with verdict != "pending" are considered fully processed.

        Args:
            post_id: Facebook post ID
            db: Database session

        Returns:
            True if post exists with completed detection, False otherwise
        """
        try:
            from models import Post

            # Check if post exists AND has completed detection (verdict != "pending")
            result = await db.execute(select(Post.post_id, Post.verdict).where(Post.post_id == post_id))
            row = result.first()

            # Only consider it "fully processed" if verdict is not "pending"
            if row and row.verdict != "pending":
                logger.info(
                    "Post exists with completed detection - media already processed",
                    post_id=post_id,
                    verdict=row.verdict,
                    status="fully_processed",
                )
                return True
            elif row:
                logger.debug(
                    "Post exists but detection pending - needs media download",
                    post_id=post_id,
                    verdict=row.verdict,
                    status="pending_detection",
                )
                return False

            return False

        except Exception as e:
            logger.error("Error checking if post exists in database", post_id=post_id, error=str(e))
            return False

    async def get_existing_gemini_uris_for_post(self, post_id: str, db: AsyncSession) -> List[str]:
        """
        Get all existing Gemini file URIs for a post from the database.
        Used when we know the post has been processed (folder exists) but need the URIs.

        Args:
            post_id: Facebook post ID
            db: Database session

        Returns:
            List of existing Gemini file URIs for the post
        """
        try:
            from models import PostMedia

            # Get all Gemini URIs for this post, regardless of media URLs
            # (since Facebook URLs change but post_id stays the same)
            media_result = await db.execute(
                select(PostMedia.gemini_file_uri).where(PostMedia.post_id == post_id).where(PostMedia.gemini_file_uri.isnot(None))
            )
            gemini_uris = [uri for (uri,) in media_result.fetchall()]

            if gemini_uris:
                logger.info("Retrieved existing Gemini URIs for processed post", post_id=post_id, uri_count=len(gemini_uris))
            else:
                logger.warning("Post folder exists but no Gemini URIs found in database", post_id=post_id)

            return gemini_uris

        except Exception as e:
            logger.error("Error retrieving existing Gemini URIs for post", post_id=post_id, error=str(e))
            return []

    async def check_existing_upload(self, post_id: str, media_url: str, db: AsyncSession) -> Optional[str]:
        """
        Check if a file for this post and media URL has already been uploaded to Gemini.

        Args:
            post_id: The Facebook post ID
            media_url: The original media URL from Facebook
            db: Database session

        Returns:
            Existing Gemini file URI if found, None otherwise
        """
        try:
            # Import here to avoid circular imports
            from models import PostMedia

            # Check if this media URL already has a Gemini file URI (simplified with direct post_id lookup)
            media_result = await db.execute(
                select(PostMedia.gemini_file_uri)
                .where(PostMedia.post_id == post_id)
                .where(PostMedia.media_url == media_url)
                .where(PostMedia.gemini_file_uri.isnot(None))
            )
            existing_uri = media_result.scalar_one_or_none()

            if existing_uri:
                logger.info(
                    "File already uploaded to Gemini, skipping upload",
                    post_id=post_id,
                    media_url=media_url[:100] + "..." if len(media_url) > 100 else media_url,
                    gemini_uri=existing_uri,
                )
                return existing_uri

            return None

        except Exception as e:
            logger.error(
                "Error checking for existing Gemini upload",
                post_id=post_id,
                media_url=media_url[:100] + "..." if len(media_url) > 100 else media_url,
                error=str(e),
            )
            return None

    async def upload_images_from_urls(
        self, image_urls: List[str], post_id: Optional[str] = None, db: Optional[AsyncSession] = None
    ) -> List[str]:
        """
        Download images from URLs and upload to Gemini File API.

        Args:
            image_urls: List of image URLs to download and upload
            post_id: Facebook post ID for deduplication (optional)
            db: Database session for deduplication check (optional)

        Returns:
            List of Gemini file URIs for uploaded images
        """
        file_uris = []

        for i, url in enumerate(image_urls):
            try:
                # Check if file already exists locally or in Gemini (if post_id and db are provided)
                # Do this BEFORE downloading to avoid unnecessary network requests
                if post_id and db:
                    # First check for existing Gemini upload
                    existing_uri = await self.check_existing_upload(post_id, url, db)
                    if existing_uri:
                        file_uris.append(existing_uri)
                        continue

                    # Then check for existing local file
                    local_path = await self.check_local_file_exists(post_id, url, db)
                    if local_path:
                        # File exists locally, upload from local file
                        file_uri = await self._upload_to_gemini_from_file(local_path, "image/jpeg", f"post_image_{i + 1}")
                        if file_uri:
                            file_uris.append(file_uri)
                            logger.info("Successfully uploaded local image to Gemini", uri=file_uri, local_path=local_path)
                        continue

                logger.info(f"Processing image {i + 1}/{len(image_urls)}", url=url[:100] + "..." if len(url) > 100 else url)

                # Download image with proper headers
                image_data, content_type = await self._download_image(url)
                if not image_data:
                    logger.warning("Failed to download image", url=url)
                    continue

                # Validate and process image
                processed_data, mime_type = await self._process_image(image_data, content_type)
                if not processed_data:
                    logger.warning("Failed to process image", url=url)
                    continue

                # Save to local file if post_id is provided
                local_file_path = None
                if post_id:
                    try:
                        local_file_path = self._get_local_file_path(post_id, url, "image")
                        with open(local_file_path, "wb") as f:
                            f.write(processed_data)
                        logger.info("Saved image locally", local_path=str(local_file_path))
                    except Exception as e:
                        logger.warning("Failed to save image locally", error=str(e))

                # Upload to Gemini
                file_uri = await self._upload_to_gemini(processed_data, mime_type, f"post_image_{i + 1}")
                if file_uri:
                    file_uris.append(file_uri)
                    logger.info("Successfully uploaded image to Gemini", uri=file_uri)

            except Exception as e:
                logger.error(f"Failed to upload image from {url}", error=str(e), url=url, exc_info=True)

        logger.info(f"Upload complete: {len(file_uris)}/{len(image_urls)} images uploaded successfully")
        return file_uris

    async def upload_videos_from_urls(
        self, video_urls: List[str], post_id: Optional[str] = None, db: Optional[AsyncSession] = None
    ) -> List[str]:
        """
        Download videos from URLs and upload to Gemini File API.

        Args:
            video_urls: List of video URLs to download and upload
            post_id: Facebook post ID for deduplication (optional)
            db: Database session for deduplication check (optional)

        Returns:
            List of Gemini file URIs for uploaded videos
        """
        file_uris = []

        for i, url in enumerate(video_urls):
            try:
                # Check if file already exists locally or in Gemini (if post_id and db are provided)
                # Do this BEFORE downloading to avoid unnecessary network requests
                if post_id and db:
                    # First check for existing Gemini upload
                    existing_uri = await self.check_existing_upload(post_id, url, db)
                    if existing_uri:
                        file_uris.append(existing_uri)
                        continue

                    # Then check for existing local file
                    local_path = await self.check_local_file_exists(post_id, url, db)
                    if local_path:
                        # File exists locally, upload from local file
                        mime_type = self._get_video_mime_type("video/mp4")  # Default, will be corrected if needed
                        file_uri = await self._upload_to_gemini_from_file(local_path, mime_type, f"post_video_{i + 1}")
                        if file_uri:
                            file_uris.append(file_uri)
                            logger.info("Successfully uploaded local video to Gemini", uri=file_uri, local_path=local_path)
                        continue

                logger.info(f"Processing video {i + 1}/{len(video_urls)}", url=url[:100] + "..." if len(url) > 100 else url)

                # Download video with proper headers
                video_data, content_type = await self._download_video(url)
                if not video_data:
                    logger.warning("Failed to download video", url=url)
                    continue

                # Validate video
                mime_type = self._get_video_mime_type(content_type)
                if not mime_type:
                    logger.warning("Unsupported video format", url=url, content_type=content_type)
                    continue

                # Save to local file if post_id is provided
                local_file_path = None
                if post_id:
                    try:
                        local_file_path = self._get_local_file_path(post_id, url, "video")
                        with open(local_file_path, "wb") as f:
                            f.write(video_data)
                        logger.info("Saved video locally", local_path=str(local_file_path))
                    except Exception as e:
                        logger.warning("Failed to save video locally", error=str(e))

                # Upload to Gemini
                file_uri = await self._upload_video_to_gemini(video_data, mime_type, f"post_video_{i + 1}")
                if file_uri:
                    file_uris.append(file_uri)
                    logger.info("Successfully uploaded video to Gemini", uri=file_uri)

            except Exception as e:
                logger.error(f"Failed to upload video from {url}", error=str(e), url=url, exc_info=True)

        logger.info(f"Video upload complete: {len(file_uris)}/{len(video_urls)} videos uploaded successfully")
        return file_uris

    async def upload_media_from_urls(
        self, image_urls: List[str], video_urls: List[str], post_id: Optional[str] = None, db: Optional[AsyncSession] = None
    ) -> Tuple[List[str], List[dict]]:
        """
        Upload both images and videos from URLs to Gemini File API.

        Args:
            image_urls: List of image URLs to upload
            video_urls: List of video URLs to upload
            post_id: Facebook post ID for deduplication (optional)
            db: Database session for deduplication check (optional)

        Returns:
            Tuple of (List of Gemini file URIs, List of media info dicts with local paths)
        """
        all_media_urls = image_urls + video_urls

        # Early exit if no media to process
        if not all_media_urls:
            return [], []

        # Sequential processing: Download ALL files first, then upload ALL files
        logger.info("Starting sequential media processing", post_id=post_id, images=len(image_urls), videos=len(video_urls))

        # Phase 1: Download all media files
        logger.info("Phase 1: Downloading all media files", post_id=post_id)
        downloaded_files = []

        # Download images first
        for i, url in enumerate(image_urls):
            try:
                # Check if already exists locally
                if post_id and db:
                    local_path = await self.check_local_file_exists(post_id, url, db)
                    if local_path:
                        downloaded_files.append({"type": "image", "url": url, "local_path": local_path, "index": i})
                        continue

                # Download and save locally
                image_data, content_type = await self._download_image(url)
                if image_data:
                    processed_data, mime_type = await self._process_image(image_data, content_type)
                    if processed_data and post_id:
                        local_file_path = self._get_local_file_path(post_id, url, "image")
                        with open(local_file_path, "wb") as f:
                            f.write(processed_data)
                        downloaded_files.append(
                            {
                                "type": "image",
                                "url": url,
                                "local_path": str(local_file_path),
                                "index": i,
                                "data": processed_data,
                                "mime_type": mime_type,
                            }
                        )
                        logger.info("Downloaded image", url=url[:50], local_path=str(local_file_path))
            except Exception as e:
                logger.error("Failed to download image", url=url, error=str(e))

        # Download videos
        for i, url in enumerate(video_urls):
            try:
                # Check if already exists locally
                if post_id and db:
                    local_path = await self.check_local_file_exists(post_id, url, db)
                    if local_path:
                        downloaded_files.append({"type": "video", "url": url, "local_path": local_path, "index": i})
                        continue

                # Download and save locally
                video_data, content_type = await self._download_video(url)
                if video_data:
                    mime_type = self._get_video_mime_type(content_type)
                    if mime_type and post_id:
                        local_file_path = self._get_local_file_path(post_id, url, "video")
                        with open(local_file_path, "wb") as f:
                            f.write(video_data)
                        downloaded_files.append(
                            {
                                "type": "video",
                                "url": url,
                                "local_path": str(local_file_path),
                                "index": i,
                                "data": video_data,
                                "mime_type": mime_type,
                            }
                        )
                        logger.info("Downloaded video", url=url[:50], local_path=str(local_file_path))
            except Exception as e:
                logger.error("Failed to download video", url=url, error=str(e))

        logger.info(
            "Phase 1 complete: Downloaded media files",
            post_id=post_id,
            downloaded=len(downloaded_files),
            total=len(image_urls) + len(video_urls),
        )

        # Phase 2: Upload all downloaded files to Gemini
        logger.info("Phase 2: Uploading all files to Gemini", post_id=post_id)
        file_uris = []

        for file_info in downloaded_files:
            try:
                # Check for existing Gemini upload
                if post_id and db:
                    existing_uri = await self.check_existing_upload(post_id, file_info["url"], db)
                    if existing_uri:
                        file_uris.append(existing_uri)
                        continue

                # Upload to Gemini from local file
                if file_info["type"] == "image":
                    file_uri = await self._upload_to_gemini_from_file(
                        file_info["local_path"], file_info.get("mime_type", "image/jpeg"), f"post_image_{file_info['index'] + 1}"
                    )
                else:  # video
                    file_uri = await self._upload_to_gemini_from_file(
                        file_info["local_path"], file_info.get("mime_type", "video/mp4"), f"post_video_{file_info['index'] + 1}"
                    )

                if file_uri:
                    file_uris.append(file_uri)
                    logger.info("Uploaded to Gemini", file_type=file_info["type"], local_path=file_info["local_path"], gemini_uri=file_uri)

            except Exception as e:
                logger.error("Failed to upload file to Gemini", file_info=file_info["url"], error=str(e))

        total_media = len(image_urls) + len(video_urls)
        logger.info(
            "Sequential media processing complete",
            post_id=post_id,
            downloaded=len(downloaded_files),
            uploaded=len(file_uris),
            total=total_media,
            success_rate=f"{len(file_uris)}/{total_media}",
        )

        return file_uris, downloaded_files

    async def _download_image(self, url: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Download image from URL.

        Args:
            url: Image URL to download

        Returns:
            Tuple of (image_data, content_type) or (None, None) if failed
        """
        try:
            import asyncio

            from clipbased_detection.utils import download_image_from_url

            logger.info("Downloading image", url=url[:100] + "..." if len(url) > 100 else url)

            # Download the image (run in thread pool since it's synchronous)
            pil_image = await asyncio.get_event_loop().run_in_executor(
                None, lambda: download_image_from_url(url, max_size=10 * 1024 * 1024, timeout=30)
            )

            # Convert PIL image to bytes
            image_buffer = io.BytesIO()
            pil_image.save(image_buffer, format="JPEG", quality=95)
            image_data = image_buffer.getvalue()

            logger.info(
                "Successfully downloaded image",
                url=url[:100] + "..." if len(url) > 100 else url,
                size_bytes=len(image_data),
                image_size=pil_image.size,
            )

            return image_data, "image/jpeg"

        except Exception as e:
            error_msg = str(e).lower()

            # Check for Facebook-specific errors that indicate URL expiration
            if any(keyword in error_msg for keyword in ["signature", "expired", "invalid", "forbidden", "403"]):
                logger.warning(
                    "Facebook URL appears to be expired or invalid", url=url[:100] + "..." if len(url) > 100 else url, error=str(e)
                )
                # For expired Facebook URLs, don't waste time on fallbacks - they won't work either
                return None, None

            logger.error("Failed to download image", url=url[:100] + "..." if len(url) > 100 else url, error=str(e), exc_info=True)

            return None, None

    async def _download_video(self, url: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Download video from URL with Facebook-compatible headers.

        Args:
            url: Video URL to download

        Returns:
            Tuple of (video_data, content_type) or (None, None) if failed
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Range": "bytes=0-",  # Support partial content for large videos
            }

            # Longer timeout for video downloads
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status in (200, 206):  # 206 for partial content
                        content_type = response.headers.get("content-type", "video/mp4")
                        data = await response.read()

                        # Validate file size (max 2GB for Gemini)
                        max_size = 2 * 1024 * 1024 * 1024  # 2GB
                        if len(data) > max_size:
                            logger.warning("Video too large for Gemini API", size=len(data), url=url)
                            return None, None

                        # Check minimum file size (avoid empty files)
                        if len(data) < 1024:  # Less than 1KB
                            logger.warning("Video file too small, might be corrupted", size=len(data), url=url)
                            return None, None

                        return data, content_type
                    else:
                        logger.warning("HTTP error downloading video", status=response.status, url=url)
                        return None, None

        except Exception as e:
            logger.error("Failed to download video", error=str(e), url=url, exc_info=True)
            return None, None

    def _get_video_mime_type(self, content_type: Optional[str]) -> Optional[str]:
        """
        Determine appropriate MIME type for video upload to Gemini.

        Args:
            content_type: Original content type from HTTP headers

        Returns:
            Validated MIME type or None if unsupported
        """
        # Supported video formats by Gemini API
        supported_formats = {
            "video/mp4": "video/mp4",
            "video/mpeg": "video/mpeg",
            "video/mov": "video/quicktime",
            "video/avi": "video/x-msvideo",
            "video/webm": "video/webm",
            "video/x-flv": "video/x-flv",
            "video/quicktime": "video/quicktime",
            "video/x-msvideo": "video/x-msvideo",
        }

        if content_type:
            # Normalize content type
            mime_type = content_type.split(";")[0].strip().lower()
            if mime_type in supported_formats:
                return supported_formats[mime_type]

        # Default fallback for unknown types
        logger.warning("Unknown video content type, defaulting to MP4", content_type=content_type)
        return "video/mp4"

    async def _process_image(self, image_data: bytes, content_type: Optional[str]) -> Tuple[Optional[bytes], str]:
        """
        Process and validate image data.

        Args:
            image_data: Raw image bytes
            content_type: Original content type

        Returns:
            Tuple of (processed_data, mime_type) or (None, mime_type) if failed
        """
        try:
            # Try to open and validate image with PIL
            with Image.open(io.BytesIO(image_data)) as img:
                # Convert to RGB if necessary (for JPEG compatibility)
                if img.mode in ("RGBA", "LA", "P"):
                    rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                    img = rgb_img

                # Resize if too large (max 4096x4096 for Gemini)
                max_size = 4096
                if img.width > max_size or img.height > max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                    logger.info(f"Resized image to {img.width}x{img.height}")

                # Save as JPEG with high quality
                output = io.BytesIO()
                img.save(output, format="JPEG", quality=85, optimize=True)
                processed_data = output.getvalue()

                return processed_data, "image/jpeg"

        except Exception as e:
            logger.error("Failed to process image", error=str(e), exc_info=True)
            return None, content_type or "image/jpeg"

    async def _upload_to_gemini(self, image_data: bytes, mime_type: str, display_name: str) -> Optional[str]:
        """
        Upload image data to Gemini File API.

        Args:
            image_data: Processed image bytes
            mime_type: MIME type of the image
            display_name: Display name for the file

        Returns:
            Gemini file URI or None if failed
        """
        try:
            # Create temporary file for upload
            import os
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                temp_file.write(image_data)
                temp_file_path = temp_file.name

            try:
                # Upload to Gemini File API
                file = genai.upload_file(path=temp_file_path, mime_type=mime_type, display_name=display_name)
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)

            # Wait for file to be processed
            import time

            max_retries = 10
            for _ in range(max_retries):
                file = genai.get_file(file.name)
                if file.state.name == "ACTIVE":
                    return file.uri
                elif file.state.name == "FAILED":
                    logger.error("Gemini file processing failed", file_name=file.name)
                    return None

                # Wait a bit before checking again
                time.sleep(1)

            logger.warning("Gemini file processing timeout", file_name=file.name)
            return None

        except Exception as e:
            logger.error("Failed to upload to Gemini", error=str(e), exc_info=True)
            return None

    async def _upload_video_to_gemini(self, video_data: bytes, mime_type: str, display_name: str) -> Optional[str]:
        """
        Upload video data to Gemini File API.

        Args:
            video_data: Video bytes
            mime_type: MIME type of the video
            display_name: Display name for the file

        Returns:
            Gemini file URI or None if failed
        """
        try:
            # Create temporary file for upload
            import os
            import tempfile

            # Determine file extension from MIME type
            extension_map = {
                "video/mp4": ".mp4",
                "video/mpeg": ".mpeg",
                "video/quicktime": ".mov",
                "video/x-msvideo": ".avi",
                "video/webm": ".webm",
                "video/x-flv": ".flv",
            }
            extension = extension_map.get(mime_type, ".mp4")

            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
                temp_file.write(video_data)
                temp_file_path = temp_file.name

            try:
                # Upload to Gemini File API
                file = genai.upload_file(path=temp_file_path, mime_type=mime_type, display_name=display_name)
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)

            # Wait for file to be processed (videos take longer)
            import time

            max_retries = 60  # Videos can take up to 1 minute to process
            for attempt in range(max_retries):
                file = genai.get_file(file.name)
                if file.state.name == "ACTIVE":
                    logger.info("Video processing complete", file_name=file.name, attempts=attempt + 1)
                    return file.uri
                elif file.state.name == "FAILED":
                    logger.error("Gemini video processing failed", file_name=file.name)
                    return None

                # Log progress for longer processing
                if attempt % 10 == 0:
                    logger.info(f"Video still processing... ({attempt + 1}/{max_retries})", file_name=file.name, state=file.state.name)

                # Wait before checking again
                time.sleep(2)  # Check every 2 seconds for videos

            logger.warning("Gemini video processing timeout", file_name=file.name)
            return None

        except Exception as e:
            logger.error("Failed to upload video to Gemini", error=str(e), exc_info=True)
            return None

    async def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """
        Clean up old uploaded files from Gemini.

        Args:
            max_age_hours: Maximum age of files to keep in hours

        Returns:
            Number of files deleted
        """
        try:
            from datetime import datetime, timedelta

            files = genai.list_files()
            deleted_count = 0
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

            for file in files:
                # Check if file is old enough to delete
                file_time = datetime.fromisoformat(file.create_time.replace("Z", "+00:00"))
                if file_time < cutoff_time:
                    try:
                        genai.delete_file(file.name)
                        deleted_count += 1
                        logger.info("Deleted old file", file_name=file.name)
                    except Exception as e:
                        logger.warning("Failed to delete file", file_name=file.name, error=str(e))

            if deleted_count > 0:
                logger.info(f"Cleanup complete: deleted {deleted_count} old files")

            return deleted_count

        except Exception as e:
            logger.error("Failed to cleanup old files", error=str(e), exc_info=True)
            return 0
