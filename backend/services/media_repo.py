from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import PostMedia
from utils.media_id_extractor import generate_composite_media_id


class MediaRepo:
    async def upsert_media(
        self,
        *,
        post_id: str,
        media_url: str,
        media_type: str,
        storage_path: Optional[str],
        mime_type: Optional[str],
        content_hash: Optional[str],
        normalized_url: Optional[str],
        gemini_file_uri: Optional[str],
        db: AsyncSession,
    ) -> None:
        media_id = generate_composite_media_id(post_id, media_url, media_type)
        stmt = insert(PostMedia).values(
            id=media_id,
            post_id=post_id,
            media_type=media_type,
            media_url=media_url,
            storage_path=storage_path,
            storage_type="local" if storage_path else None,
            mime_type=mime_type,
            content_hash=content_hash,
            normalized_url=normalized_url,
            gemini_file_uri=gemini_file_uri,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "media_url": stmt.excluded.media_url,
                "storage_path": stmt.excluded.storage_path,
                "storage_type": stmt.excluded.storage_type,
                "mime_type": stmt.excluded.mime_type,
                "content_hash": stmt.excluded.content_hash,
                "normalized_url": stmt.excluded.normalized_url,
                "gemini_file_uri": stmt.excluded.gemini_file_uri,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await db.execute(stmt)

    async def get_existing(self, *, post_id: str, media_url: str, db: AsyncSession):
        result = await db.execute(select(PostMedia).where(PostMedia.post_id == post_id).where(PostMedia.media_url == media_url))
        return result.scalar_one_or_none()

    async def delete_missing(self, *, post_id: str, valid_urls: Iterable[str], db: AsyncSession) -> int:
        stmt = delete(PostMedia).where(PostMedia.post_id == post_id).where(PostMedia.media_url.not_in(list(valid_urls)))
        res = await db.execute(stmt)
        return res.rowcount or 0
