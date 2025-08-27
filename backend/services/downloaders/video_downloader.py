from __future__ import annotations

from pathlib import Path
from typing import Optional

import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from services.downloaders.base import DownloadResult, Downloader
from services.ytdlp_video_service import YtDlpVideoService
from utils.logging import get_logger

logger = get_logger(__name__)


class VideoDownloader(Downloader):
    def __init__(self) -> None:
        self.ytdlp = YtDlpVideoService()

    async def download(self, *, post_id: str, url: str, db: AsyncSession, context: Optional[dict] = None) -> DownloadResult:
        try:
            from utils.content_deduplication import deduplication_service

            # Explicit yt-dlp directive item
            if url.startswith("yt-dlp://"):
                post_url = (context or {}).get("post_url") if context else None
                if not post_url:
                    logger.warning("yt-dlp directive provided but no post_url in context")
                    return DownloadResult(local_path=None, mime_type=None)
                video_path = await self.ytdlp.download_with_retry(post_url, post_id)
                if video_path and video_path.exists():
                    content_hash = await deduplication_service.calculate_content_hash(video_path.read_bytes())
                    return DownloadResult(local_path=video_path, mime_type="video/mp4", content_hash=content_hash)
                return DownloadResult(local_path=None, mime_type=None)

            # Handle synthetic local URLs from yt-dlp
            if url.startswith("local://yt-dlp/"):
                filename = url.split("/")[-1]
                local_path = settings.tmp_dir / post_id / "media" / filename
                if local_path.exists():
                    content_hash = await deduplication_service.calculate_content_hash(local_path.read_bytes())
                    return DownloadResult(
                        local_path=local_path,
                        mime_type="video/mp4",
                        content_hash=content_hash,
                        normalized_url=deduplication_service.normalize_facebook_url(url),
                    )
                else:
                    logger.warning("Synthetic yt-dlp path missing", expected=str(local_path))

            # Try direct HTTP download when URL is http(s)
            if url.startswith("http://") or url.startswith("https://"):
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Range": "bytes=0-",
                    "Referer": "https://www.facebook.com/",
                }
                timeout = aiohttp.ClientTimeout(total=120)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status in (200, 206):
                            data = await resp.read()
                            ctype = resp.headers.get("content-type", "").lower()
                            if len(data) >= 1024 and ctype.startswith("video/"):
                                mime_type = ctype or "video/mp4"
                                local_path = self._get_local_file_path(post_id, url, "video")
                                local_path.write_bytes(data)
                                content_hash = await deduplication_service.calculate_content_hash(data)
                                return DownloadResult(
                                    local_path=local_path,
                                    mime_type=mime_type,
                                    content_hash=content_hash,
                                    normalized_url=deduplication_service.normalize_facebook_url(url),
                                )

            # Fallback to yt-dlp using post URL if provided
            post_url = (context or {}).get("post_url") if context else None
            if post_url:
                video_path = await self.ytdlp.download_with_retry(post_url, post_id)
                if video_path and video_path.exists():
                    content_hash = await deduplication_service.calculate_content_hash(video_path.read_bytes())
                    return DownloadResult(local_path=video_path, mime_type="video/mp4", content_hash=content_hash)

            return DownloadResult(local_path=None, mime_type=None)
        except Exception as e:
            logger.error("Video download failed", url=url[:100], error=str(e), exc_info=True)
            return DownloadResult(local_path=None, mime_type=None)

    def _get_local_file_path(self, post_id: str, media_url: str, media_type: str) -> Path:
        import hashlib
        import uuid

        post_folder = settings.tmp_dir / post_id / "media"
        post_folder.mkdir(parents=True, exist_ok=True)

        url_hash = hashlib.md5(media_url.encode()).hexdigest()[:8]
        unique_id = str(uuid.uuid4())[:8]
        extension = ".mp4"
        if "." in media_url.split("/")[-1]:
            try:
                url_ext = "." + media_url.split(".")[-1].split("?")[0]
                if len(url_ext) <= 5:
                    extension = url_ext
            except (ValueError, IndexError):
                pass
        filename = f"{url_hash}_{unique_id}{extension}"
        return post_folder / filename
