"""Unified media processing service for consistent image and video handling."""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.media_registry import media_registry
from services.media_analyzer import MediaAnalyzer, MediaAnalyzerFactory, MediaFile, MediaType, AnalysisResult
from utils.logging import get_logger

logger = get_logger(__name__)


class UnifiedMediaService:
    """Unified service for processing both images and videos consistently."""

    def __init__(self, max_workers: int = 4):
        """
        Initialize unified media service.

        Args:
            max_workers: Maximum concurrent workers for processing
        """
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._semaphore = asyncio.Semaphore(max_workers)

    async def analyze_media_batch(
        self, media_urls: List[str], media_type: MediaType, post_id: str, media_info: Dict[str, Any], db: AsyncSession
    ) -> Tuple[List[Dict[str, Any]], Optional[float], Optional[float]]:
        """
        Analyze a batch of media files (images or videos) with unified processing.

        Args:
            media_urls: List of media URLs to analyze
            media_type: Type of media (IMAGE or VIDEO)
            post_id: Facebook post ID
            media_info: Database media information
            db: Database session

        Returns:
            Tuple of (results_list, average_ai_probability, average_confidence)
        """
        if not media_urls:
            return [], None, None

        media_type_str = media_type.value
        logger.info(f"Starting unified {media_type_str} analysis", post_id=post_id, count=len(media_urls))

        # Create analyzer for this media type
        analyzer = MediaAnalyzerFactory.create_analyzer(media_type)

        # Prepare media files for processing
        media_files = await self._prepare_media_files(media_urls, media_type, post_id, media_info, db)

        # Process media files in parallel batches
        results = []
        batch_size = min(self.max_workers, len(media_files))

        for i in range(0, len(media_files), batch_size):
            batch = media_files[i : i + batch_size]
            batch_results = await asyncio.gather(*[self._analyze_single_media(media_file, analyzer, post_id) for media_file in batch])
            results.extend(batch_results)

        # Clean up analyzer
        analyzer.cleanup()

        # Format results for API response
        formatted_results = self._format_results(results, media_urls, media_info)

        # Calculate aggregate metrics
        ai_probability, confidence = self._calculate_aggregates(formatted_results)

        logger.info(
            f"Completed unified {media_type_str} analysis",
            post_id=post_id,
            total=len(media_urls),
            successful=len([r for r in formatted_results if r.get("status") == "success"]),
            avg_ai_probability=round(ai_probability, 3) if ai_probability else None,
            avg_confidence=round(confidence, 3) if confidence else None,
        )

        return formatted_results, ai_probability, confidence

    async def _prepare_media_files(
        self, media_urls: List[str], media_type: MediaType, post_id: str, media_info: Dict[str, Any], db: AsyncSession
    ) -> List[MediaFile]:
        """
        Prepare media files for processing.

        Args:
            media_urls: List of media URLs
            media_type: Type of media
            post_id: Facebook post ID
            media_info: Database media information
            db: Database session

        Returns:
            List of prepared MediaFile objects
        """
        media_files = []

        for url in media_urls:
            media_file = MediaFile(url=url, media_type=media_type, post_id=post_id)

            # Check registry for existing processing
            if media_registry.is_already_processed(post_id, url, "downloaded"):
                registry_record = media_registry.get_processed_media_info(post_id, url)
                if registry_record and registry_record.local_path:
                    media_file.local_path = registry_record.local_path
                    logger.debug("Using registry cached file", url=url[:50], local_path=str(registry_record.local_path))

            # If not in registry, check database
            if not media_file.local_path:
                db_record = media_info.get(url, {})
                media_file.media_id = db_record.get("media_id")
                media_file.storage_path = db_record.get("storage_path")
                media_file.storage_type = db_record.get("storage_type")

                # Try to get local file from storage path
                local_path = await self._get_local_file(media_file, post_id, url, media_type.value)
                if local_path:
                    media_file.local_path = local_path

            media_files.append(media_file)

        return media_files

    async def _get_local_file(self, media_file: MediaFile, post_id: str, url: str, media_type_str: str) -> Optional[Path]:
        """
        Get or download local file for analysis.

        Args:
            media_file: Media file information
            post_id: Facebook post ID
            url: Media URL
            media_type_str: Media type string ('image' or 'video')

        Returns:
            Path to local file or None if not available
        """
        # CRITICAL FIX: Handle synthetic URLs for yt-dlp videos
        if url.startswith("yt-dlp://"):
            # This is a synthetic URL for yt-dlp downloaded video
            # The storage_path should contain the actual local file path
            if media_file.storage_path:
                local_path = Path(media_file.storage_path)
                if local_path.exists():
                    logger.info("Using yt-dlp downloaded video file", synthetic_url=url[:50], local_path=str(local_path))
                    return local_path
                else:
                    logger.error("yt-dlp video file not found", synthetic_url=url[:50], expected_path=str(local_path))
            return None

        # If we have a storage path, try to use it (local only)
        if media_file.storage_path:
            local_path = Path(media_file.storage_path)
            if local_path.exists():
                return local_path

        # Fallback: try to find by URL hash
        local_path = self._find_local_file_by_hash(post_id, url, media_type_str)
        if local_path and local_path.exists():
            return local_path

        return None

    def _find_local_file_by_hash(self, post_id: str, url: str, media_type_str: str) -> Optional[Path]:
        """
        Find local file by URL hash.

        Args:
            post_id: Facebook post ID
            url: Media URL
            media_type_str: Media type string

        Returns:
            Path to local file or None
        """
        import hashlib

        # Generate URL hash
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

        # Look in post media directory
        post_media_dir = settings.tmp_dir / post_id / "media"

        if post_media_dir.exists():
            # Find files matching the hash
            for file_path in post_media_dir.glob(f"*{url_hash}*"):
                if file_path.is_file():
                    # Check if it's the right type
                    if media_type_str == "image":
                        if file_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
                            return file_path
                    elif media_type_str == "video":
                        if file_path.suffix.lower() in [".mp4", ".avi", ".mov", ".webm"]:
                            return file_path

        return None

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
        import hashlib
        import uuid

        # Create post-specific media folder
        post_folder = settings.tmp_dir / post_id / "media"
        post_folder.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        url_hash = hashlib.md5(media_url.encode()).hexdigest()[:8]
        unique_id = str(uuid.uuid4())[:8]

        # Determine file extension
        extension = ".jpg" if media_type == "image" else ".mp4"
        if "." in media_url.split("/")[-1]:
            try:
                url_ext = "." + media_url.split(".")[-1].split("?")[0]
                if len(url_ext) <= 5:
                    extension = url_ext
            except (ValueError, IndexError):
                pass

        filename = f"{url_hash}_{unique_id}{extension}"
        return post_folder / filename

    async def _analyze_single_media(self, media_file: MediaFile, analyzer: MediaAnalyzer, post_id: str) -> Dict[str, Any]:
        """
        Analyze a single media file.

        Args:
            media_file: Media file to analyze
            analyzer: Media analyzer to use
            post_id: Facebook post ID

        Returns:
            Analysis result dictionary
        """
        try:
            # Check if file is available
            if not media_file.has_local_file:
                logger.warning("Local file not available for analysis", url=media_file.url[:50])
                return {
                    "url": media_file.url,
                    "status": "error",
                    "error": "File not available for analysis",
                    "media_id": media_file.media_id,
                }

            # Run analysis with semaphore to limit concurrency
            async with self._semaphore:
                result = await analyzer.analyze(media_file)

            # Update registry with analysis results
            media_key = f"{post_id}:{media_file.url}"
            media_registry.update_processing_stage(
                media_key,
                "analyzed",
                detection_result={
                    "ai_probability": result.ai_probability,
                    "confidence": result.confidence,
                    "model_used": result.model_used,
                },
            )

            # Return formatted result
            return {
                "url": media_file.url,
                "status": "success",
                "media_id": media_file.media_id,
                "local_file": str(media_file.local_path),
                **result.to_dict(),
            }

        except Exception as e:
            logger.error("Error analyzing media", url=media_file.url[:50], error=str(e), exc_info=True)
            return {"url": media_file.url, "status": "error", "error": str(e), "media_id": media_file.media_id}

    def _format_results(self, results: List[Dict[str, Any]], original_urls: List[str], media_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Format analysis results for API response.

        Args:
            results: Raw analysis results
            original_urls: Original media URLs
            media_info: Database media information

        Returns:
            Formatted results list
        """
        # Create URL to result mapping
        result_map = {r["url"]: r for r in results}

        # Format results preserving original order
        formatted = []
        for url in original_urls:
            if url in result_map:
                result = result_map[url]
            else:
                # Create error result for missing analysis
                result = {"url": url, "status": "error", "error": "Analysis not completed"}

            # Add media ID from database if not present
            if not result.get("media_id"):
                db_record = media_info.get(url, {})
                result["media_id"] = db_record.get("media_id")

            formatted.append(result)

        return formatted

    def _calculate_aggregates(self, results: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate aggregate AI probability and confidence.

        Args:
            results: Analysis results

        Returns:
            Tuple of (average_ai_probability, average_confidence)
        """
        successful_results = [r for r in results if r.get("status") == "success" and r.get("ai_probability") is not None]

        if not successful_results:
            return None, None

        # Calculate averages
        avg_ai_prob = sum(r["ai_probability"] for r in successful_results) / len(successful_results)
        avg_confidence = sum(r.get("confidence", 0.0) for r in successful_results) / len(successful_results)

        return avg_ai_prob, avg_confidence

    def cleanup(self):
        """Clean up resources."""
        self._executor.shutdown(wait=False)
