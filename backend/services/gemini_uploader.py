from __future__ import annotations

from pathlib import Path
from typing import Optional

import asyncio

import google.generativeai as genai
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models import PostMedia
from utils.logging import get_logger

logger = get_logger(__name__)


class GeminiUploader:
    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for file upload functionality")
        genai.configure(api_key=settings.gemini_api_key)

    async def ensure_uploaded(
        self,
        *,
        post_id: str,
        media_url: str,
        local_path: Path,
        mime_type: str,
        db: AsyncSession,
        display_name: Optional[str] = None,
    ) -> Optional[str]:
        try:
            # 1) DB reuse: if URI already exists, return it
            result = await db.execute(
                select(PostMedia.gemini_file_uri).where(PostMedia.post_id == post_id).where(PostMedia.media_url == media_url)
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing

            # 2) Upload from local path (run blocking SDK call in a thread)
            file = await asyncio.to_thread(
                genai.upload_file,
                path=str(local_path),
                mime_type=mime_type,
                display_name=display_name or local_path.name,
            )

            # 3) Poll until ACTIVE without blocking the event loop
            max_retries = 60 if mime_type.startswith("video/") else 10
            sleep_seconds = 2 if mime_type.startswith("video/") else 1
            for _ in range(max_retries):
                file = await asyncio.to_thread(genai.get_file, file.name)
                state = getattr(file, "state", None)
                state_name = getattr(state, "name", "") if state else ""
                if state_name == "ACTIVE":
                    return file.uri
                if state_name == "FAILED":
                    logger.error("Gemini processing failed", file_name=file.name)
                    return None
                await asyncio.sleep(sleep_seconds)

            logger.warning("Gemini processing timeout", file_name=file.name)
            return None

        except Exception as e:
            logger.error("Gemini upload error", error=str(e), local_path=str(local_path), exc_info=True)
            return None
