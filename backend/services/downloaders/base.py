from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class DownloadResult:
    local_path: Optional[Path]
    mime_type: Optional[str]
    content_hash: Optional[str] = None
    normalized_url: Optional[str] = None


class Downloader:
    async def download(
        self,
        *,
        post_id: str,
        url: str,
        db: AsyncSession,
        context: Optional[dict] = None,
    ) -> DownloadResult:
        raise NotImplementedError
