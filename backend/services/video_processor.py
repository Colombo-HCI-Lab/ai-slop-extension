"""
Video processing utilities for handling file uploads and management.
"""

import tempfile
from pathlib import Path
from typing import Dict
from urllib.parse import urlparse

import aiofiles
import aiohttp
import magic
from fastapi import UploadFile, HTTPException, status

from core.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class VideoProcessor:
    """Handles video file operations and validation."""

    def __init__(self):
        """Initialize video processor."""
        self.upload_dir = settings.upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_uploaded_file(self, upload_file: UploadFile) -> Path:
        """
        Save uploaded file to temporary location.

        Args:
            upload_file: FastAPI UploadFile object

        Returns:
            Path to saved file

        Raises:
            HTTPException: If file validation fails
        """
        # Validate file
        await self._validate_upload_file(upload_file)

        # Create unique filename
        file_extension = self._get_file_extension(upload_file.filename)
        temp_filename = f"{tempfile.mktemp(dir=self.upload_dir)}{file_extension}"
        file_path = Path(temp_filename)

        try:
            # Save file
            async with aiofiles.open(file_path, "wb") as f:
                content = await upload_file.read()
                await f.write(content)

            logger.info("File uploaded successfully", filename=upload_file.filename, file_path=str(file_path), size=len(content))
            return file_path

        except Exception as e:
            # Clean up on error
            if file_path.exists():
                file_path.unlink()
            logger.error("Failed to save uploaded file", filename=upload_file.filename, error=str(e), exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save uploaded file")

    async def _validate_upload_file(self, upload_file: UploadFile):
        """
        Validate uploaded file.

        Args:
            upload_file: FastAPI UploadFile object

        Raises:
            HTTPException: If validation fails
        """
        # Check filename
        if not upload_file.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required")

        # Check file extension
        file_extension = self._get_file_extension(upload_file.filename).lower()
        if file_extension not in settings.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported file type. Allowed: {settings.allowed_extensions}"
            )

        # Check file size (read first chunk to get size info)
        chunk_size = 8192
        total_size = 0
        upload_file.file.seek(0)

        while True:
            chunk = upload_file.file.read(chunk_size)
            if not chunk:
                break
            total_size += len(chunk)

            if total_size > settings.max_file_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Maximum size: {settings.max_file_size // (1024 * 1024)}MB",
                )

        # Reset file pointer
        upload_file.file.seek(0)

        logger.debug(
            "File validation passed", filename=upload_file.filename, size_bytes=total_size, size_mb=round(total_size / (1024 * 1024), 2)
        )

    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename."""
        return Path(filename).suffix.lower()

    def validate_mime_type(self, file_path: Path) -> bool:
        """
        Validate file MIME type using python-magic.

        Args:
            file_path: Path to file

        Returns:
            True if MIME type is valid
        """
        try:
            mime_type = magic.from_file(str(file_path), mime=True)
            is_valid = mime_type in settings.allowed_video_types
            logger.debug("File MIME type detected", file_path=str(file_path), mime_type=mime_type, is_valid=is_valid)
            return is_valid
        except Exception as e:
            logger.warning("Failed to detect MIME type", file_path=str(file_path), error=str(e))
            return False

    def get_file_info(self, file_path: Path) -> Dict:
        """
        Get file information.

        Args:
            file_path: Path to file

        Returns:
            Dictionary with file information
        """
        if not file_path.exists():
            return {}

        stat = file_path.stat()

        return {
            "filename": file_path.name,
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "extension": file_path.suffix.lower(),
        }

    def cleanup_file(self, file_path: Path):
        """
        Clean up temporary file.

        Args:
            file_path: Path to file to delete
        """
        try:
            if file_path.exists():
                file_path.unlink()
                logger.debug("File cleaned up", file_path=str(file_path))
        except Exception as e:
            logger.warning("Failed to cleanup file", file_path=str(file_path), error=str(e))

    def cleanup_old_files(self, max_age_hours: int = 24):
        """
        Clean up old temporary files.

        Args:
            max_age_hours: Maximum age in hours before cleanup
        """
        import time

        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        for file_path in self.upload_dir.iterdir():
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    self.cleanup_file(file_path)
                    logger.info("Old file cleaned up", file_path=str(file_path), age_hours=round(file_age / 3600, 1))

    def get_upload_stats(self) -> Dict:
        """Get upload directory statistics."""
        if not self.upload_dir.exists():
            return {"total_files": 0, "total_size": 0}

        total_files = 0
        total_size = 0

        for file_path in self.upload_dir.iterdir():
            if file_path.is_file():
                total_files += 1
                total_size += file_path.stat().st_size

        return {"total_files": total_files, "total_size": total_size, "upload_dir": str(self.upload_dir)}

    async def download_video_from_url(self, video_url: str) -> Path:
        """
        Download video from URL to temporary location.

        Args:
            video_url: URL of the video to download

        Returns:
            Path to downloaded file

        Raises:
            HTTPException: If download fails or validation fails
        """
        # Validate URL
        parsed_url = urlparse(video_url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid URL format")

        if parsed_url.scheme not in ["http", "https"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only HTTP/HTTPS URLs are supported")

        # Extract filename from URL or create a default one
        url_path = Path(parsed_url.path)
        if url_path.suffix.lower() in settings.allowed_extensions:
            file_extension = url_path.suffix.lower()
        else:
            file_extension = ".mp4"  # Default extension

        # Create unique filename
        temp_filename = f"{tempfile.mktemp(dir=self.upload_dir)}{file_extension}"
        file_path = Path(temp_filename)

        try:
            # Download file
            async with aiohttp.ClientSession() as session:
                async with session.get(video_url) as response:
                    # Check response status
                    if response.status != 200:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to download video: HTTP {response.status}"
                        )

                    # Check content type
                    content_type = response.headers.get("content-type", "").lower()
                    if content_type and not any(mime in content_type for mime in settings.allowed_video_types):
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid video content type: {content_type}")

                    # Check content length if available
                    content_length = response.headers.get("content-length")
                    if content_length and int(content_length) > settings.max_file_size:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File too large. Maximum size: {settings.max_file_size // (1024 * 1024)}MB",
                        )

                    # Download and save file
                    total_size = 0
                    async with aiofiles.open(file_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            total_size += len(chunk)

                            # Check size during download
                            if total_size > settings.max_file_size:
                                raise HTTPException(
                                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                    detail=f"File too large. Maximum size: {settings.max_file_size // (1024 * 1024)}MB",
                                )

                            await f.write(chunk)

            # Validate downloaded file
            if not self.validate_mime_type(file_path):
                self.cleanup_file(file_path)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video file format")

            logger.info(
                "Video downloaded from URL",
                video_url=video_url,
                file_path=str(file_path),
                size_bytes=total_size,
                size_mb=round(total_size / (1024 * 1024), 2),
            )
            return file_path

        except aiohttp.ClientError as e:
            # Clean up on network error
            if file_path.exists():
                file_path.unlink()
            logger.error("Failed to download video from URL", video_url=video_url, error=str(e), error_type=type(e).__name__, exc_info=True)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to download video from URL")
        except Exception as e:
            # Clean up on any other error
            if file_path.exists():
                file_path.unlink()
            logger.error("Failed to download video from URL", video_url=video_url, error=str(e), error_type=type(e).__name__, exc_info=True)
            raise
