from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from services.downloaders.base import DownloadResult, Downloader
from utils.logging import get_logger

logger = get_logger(__name__)


class ImageDownloader(Downloader):
    async def download(self, *, post_id: str, url: str, db: AsyncSession, context: Optional[dict] = None) -> DownloadResult:
        try:
            # Check registry/DB for existing local file handled by pipeline; here we only download
            import asyncio
            from ml.clipbased.impl.utils import download_image_from_url
            from utils.content_deduplication import deduplication_service

            logger.info("Downloading image", url=url[:100] + "..." if len(url) > 100 else url)

            pil_image = await asyncio.get_event_loop().run_in_executor(
                None, lambda: download_image_from_url(url, max_size=10 * 1024 * 1024, timeout=30)
            )

            # Convert/validate
            if pil_image.mode in ("RGBA", "LA", "P"):
                rgb_img = Image.new("RGB", pil_image.size, (255, 255, 255))
                if pil_image.mode == "P":
                    pil_image = pil_image.convert("RGBA")
                rgb_img.paste(pil_image, mask=pil_image.split()[-1] if pil_image.mode in ("RGBA", "LA") else None)
                pil_image = rgb_img

            max_size = 4096
            if pil_image.width > max_size or pil_image.height > max_size:
                pil_image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Save to bytes and compute hash
            output = io.BytesIO()
            pil_image.save(output, format="JPEG", quality=85, optimize=True)
            data = output.getvalue()

            content_hash = await deduplication_service.calculate_content_hash(data)

            # Persist to local storage
            post_dir = settings.tmp_dir / post_id / "media"
            post_dir.mkdir(parents=True, exist_ok=True)
            # Reuse path generation from content_detection_service._get_local_file_path style
            local_path = self._get_local_file_path(post_id, url, "image")
            local_path.write_bytes(data)

            logger.info("Image saved locally", path=str(local_path), size_bytes=len(data))
            return DownloadResult(
                local_path=local_path,
                mime_type="image/jpeg",
                content_hash=content_hash,
                normalized_url=deduplication_service.normalize_facebook_url(url),
            )
        except Exception as e:
            logger.error("Image download failed", url=url[:100], error=str(e), exc_info=True)
            return DownloadResult(local_path=None, mime_type=None)

    def _get_local_file_path(self, post_id: str, media_url: str, media_type: str) -> Path:
        import hashlib
        import uuid

        post_folder = settings.tmp_dir / post_id / "media"
        post_folder.mkdir(parents=True, exist_ok=True)

        url_hash = hashlib.md5(media_url.encode()).hexdigest()[:8]
        unique_id = str(uuid.uuid4())[:8]
        extension = ".jpg"
        if "." in media_url.split("/")[-1]:
            try:
                url_ext = "." + media_url.split(".")[-1].split("?")[0]
                if len(url_ext) <= 5:
                    extension = url_ext
            except (ValueError, IndexError):
                pass
        filename = f"{url_hash}_{unique_id}{extension}"
        return post_folder / filename
