"""File upload service for handling image and video uploads to Gemini File API."""

import io
from typing import List, Optional, Tuple, Union

import aiohttp
import google.generativeai as genai
from PIL import Image

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

    async def upload_images_from_urls(self, image_urls: List[str]) -> List[str]:
        """
        Download images from URLs and upload to Gemini File API.

        Args:
            image_urls: List of image URLs to download and upload

        Returns:
            List of Gemini file URIs for uploaded images
        """
        file_uris = []

        for i, url in enumerate(image_urls):
            try:
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

                # Upload to Gemini
                file_uri = await self._upload_to_gemini(processed_data, mime_type, f"post_image_{i + 1}")
                if file_uri:
                    file_uris.append(file_uri)
                    logger.info("Successfully uploaded image to Gemini", uri=file_uri)

            except Exception as e:
                logger.error(f"Failed to upload image from {url}", error=str(e), url=url, exc_info=True)

        logger.info(f"Upload complete: {len(file_uris)}/{len(image_urls)} images uploaded successfully")
        return file_uris

    async def upload_videos_from_urls(self, video_urls: List[str]) -> List[str]:
        """
        Download videos from URLs and upload to Gemini File API.

        Args:
            video_urls: List of video URLs to download and upload

        Returns:
            List of Gemini file URIs for uploaded videos
        """
        file_uris = []

        for i, url in enumerate(video_urls):
            try:
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

                # Upload to Gemini
                file_uri = await self._upload_video_to_gemini(video_data, mime_type, f"post_video_{i + 1}")
                if file_uri:
                    file_uris.append(file_uri)
                    logger.info("Successfully uploaded video to Gemini", uri=file_uri)

            except Exception as e:
                logger.error(f"Failed to upload video from {url}", error=str(e), url=url, exc_info=True)

        logger.info(f"Video upload complete: {len(file_uris)}/{len(video_urls)} videos uploaded successfully")
        return file_uris

    async def upload_media_from_urls(self, image_urls: List[str], video_urls: List[str]) -> List[str]:
        """
        Upload both images and videos from URLs to Gemini File API.

        Args:
            image_urls: List of image URLs to upload
            video_urls: List of video URLs to upload

        Returns:
            List of Gemini file URIs for all uploaded media
        """
        file_uris = []

        # Upload images
        if image_urls:
            image_uris = await self.upload_images_from_urls(image_urls)
            file_uris.extend(image_uris)

        # Upload videos
        if video_urls:
            video_uris = await self.upload_videos_from_urls(video_urls)
            file_uris.extend(video_uris)

        total_media = len(image_urls) + len(video_urls)
        logger.info(f"All media upload complete: {len(file_uris)}/{total_media} files uploaded successfully", 
                   images=len(image_urls), videos=len(video_urls), successful=len(file_uris))
        
        return file_uris

    async def _download_image(self, url: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Download image from URL with Facebook-compatible headers.

        Args:
            url: Image URL to download

        Returns:
            Tuple of (image_data, content_type) or (None, None) if failed
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        content_type = response.headers.get("content-type", "image/jpeg")
                        data = await response.read()

                        # Validate file size (max 20MB for Gemini)
                        if len(data) > 20 * 1024 * 1024:
                            logger.warning("Image too large for Gemini API", size=len(data), url=url)
                            return None, None

                        return data, content_type
                    else:
                        logger.warning("HTTP error downloading image", status=response.status, url=url)
                        return None, None

        except Exception as e:
            logger.error("Failed to download image", error=str(e), url=url, exc_info=True)
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
            mime_type = content_type.split(';')[0].strip().lower()
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
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
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
            import tempfile
            import os
            
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
