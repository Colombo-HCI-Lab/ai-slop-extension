"""Google Cloud Storage service for handling media file storage."""

import hashlib
import uuid
from typing import Optional

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

from core.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class GCSStorageService:
    """Handles media file storage in Google Cloud Storage."""

    def __init__(self):
        """Initialize the GCS storage service."""
        # GCS is now required - validate configuration
        if not settings.gcs_bucket_name:
            raise ValueError("GCS_BUCKET_NAME is required for media storage. Please set GCS_BUCKET_NAME in your environment variables.")

        try:
            # Initialize GCS client
            if settings.gcs_credentials_path:
                self.client = storage.Client.from_service_account_json(settings.gcs_credentials_path, project=settings.gcs_project_id)
            else:
                # Use Application Default Credentials
                self.client = storage.Client(project=settings.gcs_project_id)

            self.bucket = self.client.bucket(settings.gcs_bucket_name)

            # Test bucket access by attempting to get bucket metadata
            _ = self.bucket.reload()

            logger.info("GCS storage service initialized successfully", bucket=settings.gcs_bucket_name, project=self.client.project)

        except Exception as e:
            logger.error("Failed to initialize GCS client", bucket=settings.gcs_bucket_name, project=settings.gcs_project_id, error=str(e))
            raise RuntimeError(
                f"Failed to connect to GCS bucket '{settings.gcs_bucket_name}'. "
                f"Please verify: 1) Bucket exists, 2) Credentials are valid, "
                f"3) Service account has storage permissions. Error: {str(e)}"
            ) from e

    def is_available(self) -> bool:
        """Check if GCS is available for use."""
        return self.client is not None and self.bucket is not None

    def get_media_path(self, post_id: str, media_url: str, media_type: str) -> str:
        """
        Generate GCS object path for media storage.

        Args:
            post_id: Facebook post ID
            media_url: Original media URL
            media_type: 'image' or 'video'

        Returns:
            GCS object path: {post_id}/media/{hash}_{uuid}.ext
        """
        # Generate unique filename based on URL hash and UUID
        url_hash = hashlib.md5(media_url.encode()).hexdigest()[:8]
        unique_id = str(uuid.uuid4())[:8]

        # Determine file extension from URL or use default
        extension = ".jpg" if media_type == "image" else ".mp4"
        if "." in media_url.split("/")[-1]:
            try:
                url_ext = "." + media_url.split(".")[-1].split("?")[0]
                if len(url_ext) <= 5:  # Reasonable extension length
                    extension = url_ext
            except (ValueError, IndexError):
                pass

        filename = f"{url_hash}_{unique_id}{extension}"
        return f"{post_id}/media/{filename}"

    async def upload_media(self, data: bytes, gcs_path: str, content_type: str) -> str:
        """
        Upload media data to GCS.

        Args:
            data: Media file bytes
            gcs_path: GCS object path
            content_type: MIME type of the media

        Returns:
            GCS URI: gs://{bucket_name}/{gcs_path}

        Raises:
            Exception: If GCS is not available or upload fails
        """
        if not self.is_available():
            raise Exception("GCS storage is not available")

        try:
            blob = self.bucket.blob(gcs_path)
            blob.upload_from_string(data, content_type=content_type)

            # Set cache control for media files (1 year)
            blob.cache_control = "public, max-age=31536000"
            blob.patch()

            gcs_uri = f"gs://{settings.gcs_bucket_name}/{gcs_path}"
            logger.info("Successfully uploaded media to GCS", gcs_path=gcs_path, size_bytes=len(data), content_type=content_type)

            return gcs_uri

        except GoogleCloudError as e:
            logger.error("GCS upload failed", gcs_path=gcs_path, error=str(e), exc_info=True)
            raise
        except Exception as e:
            logger.error("Unexpected error during GCS upload", gcs_path=gcs_path, error=str(e), exc_info=True)
            raise

    async def media_exists(self, gcs_path: str) -> bool:
        """
        Check if media file already exists in GCS.

        Args:
            gcs_path: GCS object path

        Returns:
            True if file exists, False otherwise
        """
        if not self.is_available():
            return False

        try:
            blob = self.bucket.blob(gcs_path)
            return blob.exists()
        except Exception as e:
            logger.warning("Error checking GCS file existence", gcs_path=gcs_path, error=str(e))
            return False

    async def download_media(self, gcs_path: str) -> bytes:
        """
        Download media data from GCS.

        Args:
            gcs_path: GCS object path

        Returns:
            Media file bytes

        Raises:
            Exception: If GCS is not available or download fails
        """
        if not self.is_available():
            raise Exception("GCS storage is not available")

        try:
            blob = self.bucket.blob(gcs_path)
            data = blob.download_as_bytes()
            logger.debug("Downloaded media from GCS", gcs_path=gcs_path, size_bytes=len(data))
            return data

        except GoogleCloudError as e:
            logger.error("GCS download failed", gcs_path=gcs_path, error=str(e), exc_info=True)
            raise
        except Exception as e:
            logger.error("Unexpected error during GCS download", gcs_path=gcs_path, error=str(e), exc_info=True)
            raise

    async def delete_media(self, gcs_path: str) -> bool:
        """
        Delete media file from GCS.

        Args:
            gcs_path: GCS object path

        Returns:
            True if deletion successful, False otherwise
        """
        if not self.is_available():
            return False

        try:
            blob = self.bucket.blob(gcs_path)
            blob.delete()
            logger.info("Deleted media from GCS", gcs_path=gcs_path)
            return True

        except GoogleCloudError as e:
            logger.error("GCS deletion failed", gcs_path=gcs_path, error=str(e), exc_info=True)
            return False
        except Exception as e:
            logger.error("Unexpected error during GCS deletion", gcs_path=gcs_path, error=str(e), exc_info=True)
            return False

    def gcs_uri_to_path(self, gcs_uri: str) -> str:
        """
        Convert GCS URI to object path.

        Args:
            gcs_uri: GCS URI (gs://bucket/path)

        Returns:
            Object path within bucket
        """
        if gcs_uri.startswith(f"gs://{settings.gcs_bucket_name}/"):
            return gcs_uri.replace(f"gs://{settings.gcs_bucket_name}/", "")
        return gcs_uri

    async def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """
        Clean up old media files from GCS.

        Args:
            max_age_hours: Maximum age of files to keep in hours

        Returns:
            Number of files deleted
        """
        if not self.is_available():
            logger.warning("Cannot cleanup GCS files - storage not available")
            return 0

        try:
            from datetime import datetime, timedelta, timezone

            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
            deleted_count = 0

            # List all blobs (no prefix needed since post_id is now at root)
            blobs = self.client.list_blobs(self.bucket)

            for blob in blobs:
                if blob.time_created < cutoff_time:
                    try:
                        blob.delete()
                        deleted_count += 1
                        logger.debug("Deleted old GCS file", name=blob.name, created=blob.time_created)
                    except Exception as e:
                        logger.warning("Failed to delete old GCS file", name=blob.name, error=str(e))

            if deleted_count > 0:
                logger.info(f"GCS cleanup complete: deleted {deleted_count} old files")

            return deleted_count

        except Exception as e:
            logger.error("Failed to cleanup old GCS files", error=str(e), exc_info=True)
            return 0

    def get_public_url(self, gcs_path: str) -> Optional[str]:
        """
        Get public URL for a GCS object (if bucket is public).

        Args:
            gcs_path: GCS object path

        Returns:
            Public URL or None if not available
        """
        if not self.is_available():
            return None

        try:
            blob = self.bucket.blob(gcs_path)
            # Return public URL if bucket allows public access
            return blob.public_url
        except Exception as e:
            logger.warning("Error getting public URL", gcs_path=gcs_path, error=str(e))
            return None
