from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from core.media_registry import media_registry
from services.downloaders.base import DownloadResult
from services.downloaders.image_downloader import ImageDownloader
from services.downloaders.video_downloader import VideoDownloader
from services.gemini_uploader import GeminiUploader
from services.media_repo import MediaRepo
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MediaItem:
    url: str
    media_type: str  # 'image' or 'video'


@dataclass
class MediaRecord:
    url: str
    media_type: str
    storage_path: Optional[str]
    gemini_uri: Optional[str]


class MediaPipeline:
    def __init__(self) -> None:
        self.image_downloader = ImageDownloader()
        self.video_downloader = VideoDownloader()
        self.uploader = GeminiUploader()
        self.repo = MediaRepo()

    async def process_media(
        self,
        *,
        post_id: str,
        items: List[MediaItem],
        db: AsyncSession,
        context: Optional[dict] = None,
    ) -> List[MediaRecord]:
        records: List[MediaRecord] = []

        # Optional: find duplicate content by URL mapping for reuse
        duplicates: Dict[str, str] = {}
        try:
            from utils.content_deduplication import deduplication_service

            all_urls = [item.url for item in items]
            duplicates = await deduplication_service.find_duplicate_content(post_id, all_urls, db)
            if duplicates:
                logger.info("Found duplicate content for media batch", post_id=post_id, duplicate_count=len(duplicates))
        except Exception:
            pass

        for index, item in enumerate(items):
            url = item.url
            media_type = item.media_type
            try:
                # Registry: already processed?
                if media_registry.is_already_processed(post_id, url, "downloaded"):
                    existing = media_registry.get_processed_media_info(post_id, url)
                    if existing and existing.storage_path:
                        storage_path = existing.storage_path
                        gemini_uri = None
                        # Ensure Gemini existing
                        if media_registry.is_already_processed(post_id, url, "uploaded") and existing.gemini_uri:
                            gemini_uri = existing.gemini_uri
                        else:
                            gemini_uri = await self._ensure_gemini(post_id, url, Path(storage_path), media_type, db, index)
                            media_registry.update_processing_stage(f"{post_id}:{url}", "uploaded", gemini_uri=gemini_uri)

                        await self.repo.upsert_media(
                            post_id=post_id,
                            media_url=url,
                            media_type=media_type,
                            storage_path=storage_path,
                            mime_type=self._default_mime(media_type),
                            content_hash=None,
                            normalized_url=None,
                            gemini_file_uri=gemini_uri,
                            db=db,
                        )
                        records.append(MediaRecord(url=url, media_type=media_type, storage_path=storage_path, gemini_uri=gemini_uri))
                        continue

                # DB: existing storage?
                existing_db = await self.repo.get_existing(post_id=post_id, media_url=url, db=db)
                if existing_db and existing_db.storage_path:
                    storage_path = existing_db.storage_path
                    gemini_uri = existing_db.gemini_file_uri
                    if not gemini_uri:
                        gemini_uri = await self._ensure_gemini(post_id, url, Path(storage_path), media_type, db, index)
                    await self.repo.upsert_media(
                        post_id=post_id,
                        media_url=url,
                        media_type=media_type,
                        storage_path=storage_path,
                        mime_type=existing_db.mime_type or self._default_mime(media_type),
                        content_hash=existing_db.content_hash,
                        normalized_url=existing_db.normalized_url,
                        gemini_file_uri=gemini_uri,
                        db=db,
                    )
                    records.append(MediaRecord(url=url, media_type=media_type, storage_path=storage_path, gemini_uri=gemini_uri))
                    continue

                # Duplicate reuse
                if url in duplicates:
                    storage_path = duplicates[url]
                    gemini_uri = await self._ensure_gemini(post_id, url, Path(storage_path), media_type, db, index)
                    await self.repo.upsert_media(
                        post_id=post_id,
                        media_url=url,
                        media_type=media_type,
                        storage_path=storage_path,
                        mime_type=self._default_mime(media_type),
                        content_hash=None,
                        normalized_url=None,
                        gemini_file_uri=gemini_uri,
                        db=db,
                    )
                    records.append(MediaRecord(url=url, media_type=media_type, storage_path=storage_path, gemini_uri=gemini_uri))
                    continue

                # Download via type-specific downloader
                dl: DownloadResult
                if media_type == "image":
                    dl = await self.image_downloader.download(post_id=post_id, url=url, db=db, context=context)
                else:
                    dl = await self.video_downloader.download(post_id=post_id, url=url, db=db, context=context)

                if not dl.local_path:
                    logger.warning("Skipping media without local file", url=url[:100])
                    continue

                # Register and ensure Gemini upload
                media_registry.register_media(post_id, url, media_type)
                media_registry.update_processing_stage(
                    f"{post_id}:{url}", "downloaded", local_path=dl.local_path, storage_path=str(dl.local_path)
                )
                gemini_uri = await self._ensure_gemini(post_id, url, dl.local_path, media_type, db, index)
                media_registry.update_processing_stage(f"{post_id}:{url}", "uploaded", gemini_uri=gemini_uri)

                # Upsert DB
                await self.repo.upsert_media(
                    post_id=post_id,
                    media_url=url,
                    media_type=media_type,
                    storage_path=str(dl.local_path),
                    mime_type=dl.mime_type or self._default_mime(media_type),
                    content_hash=dl.content_hash,
                    normalized_url=dl.normalized_url,
                    gemini_file_uri=gemini_uri,
                    db=db,
                )

                records.append(MediaRecord(url=url, media_type=media_type, storage_path=str(dl.local_path), gemini_uri=gemini_uri))

            except Exception as e:
                logger.error("Media processing failed", url=url[:80], error=str(e), exc_info=True)

        # Commit once at the end for performance
        await db.commit()
        return records

    async def _ensure_gemini(
        self, post_id: str, url: str, local_path: Path, media_type: str, db: AsyncSession, index: int
    ) -> Optional[str]:
        mime = self._default_mime(media_type)
        display = f"post_{media_type}_{index + 1}"
        return await self.uploader.ensure_uploaded(
            post_id=post_id, media_url=url, local_path=local_path, mime_type=mime, db=db, display_name=display
        )

    def _default_mime(self, media_type: str) -> str:
        return "image/jpeg" if media_type == "image" else "video/mp4"
