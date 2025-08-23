"""
Video download service using yt-dlp for Facebook video extraction.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import yt_dlp

from core.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class YtDlpVideoService:
    """Service for downloading Facebook videos using yt-dlp."""

    def __init__(self):
        """Initialize the yt-dlp video service."""
        self.base_output_dir = settings.tmp_dir / "posts"
        self.base_output_dir.mkdir(parents=True, exist_ok=True)

        # Base yt-dlp options
        self.base_ydl_opts = {
            "quiet": True,
            "no_warnings": False,
            "extract_flat": False,
            "format": "best[ext=mp4]/best[ext=webm]/best",  # Prefer MP4, fallback to WebM
            "socket_timeout": 30,
            "retries": 3,
            "fragment_retries": 3,
            "ignoreerrors": False,
            "nocheckcertificate": True,  # Facebook sometimes has cert issues
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "referer": "https://www.facebook.com/",
            # Disable post-processing for speed
            "postprocessors": [],
            # Add network options
            "http_chunk_size": 10485760,  # 10MB chunks
        }

    def _get_output_path(self, post_id: str, video_index: int = 0) -> Path:
        """
        Generate output path for video file.

        Args:
            post_id: Facebook post ID
            video_index: Index of video in post (for multiple videos)

        Returns:
            Path object for video output
        """
        output_dir = self.base_output_dir / post_id / "media"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / f"video_{video_index}.%(ext)s"

    async def extract_video_info(self, url: str) -> Optional[Dict]:
        """
        Extract video information without downloading.

        Args:
            url: Facebook post or video URL

        Returns:
            Video metadata dict or None if extraction fails
        """
        try:
            # Use subprocess for better isolation
            cmd = ["yt-dlp", "--dump-json", "--no-playlist", "--no_warnings", url]

            logger.info("Extracting video info", url=url[:100])

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            proc = await loop.run_in_executor(None, lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=30))

            if proc.returncode == 0 and proc.stdout:
                info = json.loads(proc.stdout)
                logger.info(
                    "Video info extracted", title=info.get("title", "Unknown")[:50], duration=info.get("duration"), format=info.get("ext")
                )
                return info
            else:
                logger.warning("Failed to extract video info", stderr=proc.stderr[:500] if proc.stderr else "No error output")
                return None

        except subprocess.TimeoutExpired:
            logger.error("Video info extraction timeout", url=url[:100])
            return None
        except json.JSONDecodeError as e:
            logger.error("Failed to parse video info JSON", error=str(e))
            return None
        except Exception as e:
            logger.error("Video info extraction failed", url=url[:100], error=str(e))
            return None

    async def download_facebook_video(
        self, url: str, post_id: str, video_index: int = 0, cookies_file: Optional[str] = None
    ) -> Optional[Path]:
        """
        Download a Facebook video using yt-dlp.

        Args:
            url: Facebook post or video URL
            post_id: Facebook post ID for organizing downloads
            video_index: Index of video in post (for multiple videos)
            cookies_file: Optional path to cookies file for authentication

        Returns:
            Path to downloaded video file or None if download fails
        """
        try:
            output_template = str(self._get_output_path(post_id, video_index))

            # Configure yt-dlp options
            ydl_opts = self.base_ydl_opts.copy()
            ydl_opts["outtmpl"] = output_template

            # Add cookies if provided
            if cookies_file and Path(cookies_file).exists():
                ydl_opts["cookiefile"] = cookies_file
                logger.info("Using cookies file for authentication", cookies_file=cookies_file)

            # Progress hook for logging
            def progress_hook(d):
                if d["status"] == "downloading":
                    percent = d.get("_percent_str", "N/A")
                    speed = d.get("_speed_str", "N/A")
                    logger.debug(f"Downloading video: {percent} at {speed}")
                elif d["status"] == "finished":
                    logger.info("Download finished, processing...")

            ydl_opts["progress_hooks"] = [progress_hook]

            logger.info("Starting video download", url=url[:100], post_id=post_id)

            # Download using yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                if not info:
                    logger.error("No video info extracted")
                    return None

                # Get the actual output filename
                filename = ydl.prepare_filename(info)
                # Replace extension template with actual extension
                actual_ext = info.get("ext", "mp4")
                filename = filename.replace(".%(ext)s", f".{actual_ext}")

                output_path = Path(filename)

                if output_path.exists() and output_path.stat().st_size > 0:
                    logger.info(
                        "Video downloaded successfully",
                        post_id=post_id,
                        path=str(output_path),
                        size_mb=round(output_path.stat().st_size / (1024 * 1024), 2),
                        format=actual_ext,
                    )
                    return output_path
                else:
                    logger.error("Downloaded file is empty or doesn't exist", path=str(output_path))
                    return None

        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if "Private video" in error_msg:
                logger.warning("Video is private, may need authentication", url=url[:100])
            elif "URL could be a direct video link" in error_msg:
                # Try direct download for blob URLs or direct links
                logger.info("Attempting direct download fallback")
                return await self._download_direct_video(url, post_id, video_index)
            else:
                logger.error("yt-dlp download error", url=url[:100], error=error_msg[:500])
            return None
        except Exception as e:
            logger.error("Video download failed", url=url[:100], post_id=post_id, error=str(e))
            return None

    async def _download_direct_video(self, url: str, post_id: str, video_index: int = 0) -> Optional[Path]:
        """
        Fallback method for direct video download.

        Args:
            url: Direct video URL
            post_id: Facebook post ID
            video_index: Video index in post

        Returns:
            Path to downloaded video or None
        """
        try:
            import aiohttp

            output_dir = self.base_output_dir / post_id / "media"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"video_{video_index}.mp4"

            logger.info("Attempting direct video download", url=url[:100])

            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": "https://www.facebook.com/"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        content = await response.read()

                        with open(output_path, "wb") as f:
                            f.write(content)

                        if output_path.stat().st_size > 0:
                            logger.info("Direct download successful", path=str(output_path))
                            return output_path

            return None

        except Exception as e:
            logger.error("Direct download failed", error=str(e))
            return None

    async def download_post_videos(self, post_url: str, post_id: str, expected_video_count: int = 1) -> List[Path]:
        """
        Download all videos from a Facebook post.

        Args:
            post_url: URL of the Facebook post
            post_id: Facebook post ID
            expected_video_count: Expected number of videos in post

        Returns:
            List of paths to downloaded videos
        """
        downloaded_videos = []

        try:
            # First, try to download the entire post
            video_path = await self.download_facebook_video(post_url, post_id, 0)
            if video_path:
                downloaded_videos.append(video_path)

            # If we expect more videos, try to extract them individually
            if expected_video_count > 1:
                logger.info(f"Post may contain {expected_video_count} videos, checking...")
                # This would require more sophisticated extraction
                # For now, yt-dlp should handle multi-video posts automatically

            logger.info(
                "Post video download complete",
                post_id=post_id,
                downloaded_count=len(downloaded_videos),
                expected_count=expected_video_count,
            )

        except Exception as e:
            logger.error("Failed to download post videos", post_id=post_id, error=str(e))

        return downloaded_videos

    async def download_with_retry(self, url: str, post_id: str, max_retries: int = 3) -> Optional[Path]:
        """
        Download video with retry logic.

        Args:
            url: Video URL
            post_id: Post ID
            max_retries: Maximum number of retry attempts

        Returns:
            Path to downloaded video or None
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"Download attempt {attempt + 1}/{max_retries}", url=url[:100])

                result = await self.download_facebook_video(url, post_id)
                if result:
                    return result

                # Wait before retry
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)  # Exponential backoff

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed", error=str(e))
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)

        logger.error("All download attempts failed", url=url[:100])
        return None

    def cleanup_old_videos(self, max_age_hours: int = 24) -> int:
        """
        Clean up old downloaded videos.

        Args:
            max_age_hours: Maximum age in hours before cleanup

        Returns:
            Number of files deleted
        """
        import time

        deleted_count = 0
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        try:
            for post_dir in self.base_output_dir.iterdir():
                if post_dir.is_dir():
                    media_dir = post_dir / "media"
                    if media_dir.exists():
                        for video_file in media_dir.glob("video_*"):
                            if video_file.is_file():
                                file_age = current_time - video_file.stat().st_mtime
                                if file_age > max_age_seconds:
                                    video_file.unlink()
                                    deleted_count += 1
                                    logger.info("Deleted old video", path=str(video_file))

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old video files")

        except Exception as e:
            logger.error("Cleanup failed", error=str(e))

        return deleted_count
