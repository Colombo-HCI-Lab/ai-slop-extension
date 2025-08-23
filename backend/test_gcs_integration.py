#!/usr/bin/env python3
"""Test script for GCS storage integration."""

import asyncio
import os
from pathlib import Path

from services.gcs_storage_service import GCSStorageService
from core.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


def test_error_handling():
    """Test error handling when GCS is not properly configured."""
    print("\n❌ Testing Error Handling")
    print("-" * 30)
    
    # Test 1: Empty bucket name
    original_bucket = settings.gcs_bucket_name
    try:
        # Temporarily clear bucket name
        settings.gcs_bucket_name = ""
        gcs_service = GCSStorageService()
        print("❌ ERROR: Should have failed with empty bucket name")
    except ValueError as e:
        print(f"✅ Correctly caught ValueError: {str(e)}")
    except Exception as e:
        print(f"⚠️  Unexpected error type: {type(e).__name__}: {str(e)}")
    finally:
        # Restore original bucket name
        settings.gcs_bucket_name = original_bucket
    
    # Test 2: Invalid credentials (if bucket is configured but credentials are bad)
    if settings.gcs_bucket_name and not settings.gcs_bucket_name.startswith("#"):
        try:
            # This should fail if the bucket doesn't exist or credentials are invalid
            gcs_service = GCSStorageService()
            print(f"⚠️  GCS service initialized successfully (bucket: {settings.gcs_bucket_name})")
            print("   This means GCS is properly configured in your environment")
        except RuntimeError as e:
            print(f"✅ Correctly caught connection error: {str(e)}")
        except Exception as e:
            print(f"⚠️  Unexpected error type: {type(e).__name__}: {str(e)}")


async def test_gcs_integration():
    """Test GCS storage service integration."""
    print("🚀 Testing GCS Storage Integration")
    print("=" * 50)
    
    try:
        # Test initialization
        gcs_service = GCSStorageService()
        print(f"GCS Available: {gcs_service.is_available()}")
        print(f"Bucket: {settings.gcs_bucket_name}")
        print(f"Project: {settings.gcs_project_id}")
        print(f"Local Fallback: {settings.enable_local_fallback}")
        
        if not gcs_service.is_available():
            print("⚠️  GCS not available - this is normal if not configured")
            print("   Set GCS_BUCKET_NAME in your environment to test GCS")
            return
    except (ValueError, RuntimeError) as e:
        print(f"⚠️  GCS service initialization failed: {str(e)}")
        print("   This is expected when GCS is not properly configured")
        return
    
    # Test basic operations
    test_data = b"Hello, GCS Storage!"
    test_path = "test/sample.txt"
    content_type = "text/plain"
    
    try:
        print(f"\n📤 Testing upload to: {test_path}")
        gcs_uri = await gcs_service.upload_media(test_data, test_path, content_type)
        print(f"✅ Upload successful: {gcs_uri}")
        
        print(f"\n🔍 Testing file existence check")
        exists = await gcs_service.media_exists(test_path)
        print(f"✅ File exists: {exists}")
        
        print(f"\n📥 Testing download")
        downloaded_data = await gcs_service.download_media(test_path)
        print(f"✅ Download successful: {len(downloaded_data)} bytes")
        print(f"   Content matches: {downloaded_data == test_data}")
        
        print(f"\n🗑️  Testing deletion")
        deleted = await gcs_service.delete_media(test_path)
        print(f"✅ Deletion successful: {deleted}")
        
        print(f"\n🔍 Testing file existence after deletion")
        exists_after = await gcs_service.media_exists(test_path)
        print(f"✅ File exists after deletion: {exists_after}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.error("GCS test failed", error=str(e), exc_info=True)


def test_path_generation():
    """Test media path generation."""
    print("\n🛤️  Testing Path Generation")
    print("-" * 30)
    
    try:
        gcs_service = GCSStorageService()
        
        # Test path generation
        post_id = "test_post_123"
        media_url = "https://example.com/image.jpg?param=value"
        
        image_path = gcs_service.get_media_path(post_id, media_url, "image")
        video_path = gcs_service.get_media_path(post_id, media_url, "video")
        
        print(f"Image path: {image_path}")
        print(f"Video path: {video_path}")
        print(f"Paths are different: {image_path != video_path}")
    except (ValueError, RuntimeError) as e:
        print(f"⚠️  Cannot test path generation - GCS not properly configured: {str(e)}")
        print("   This is expected if GCS credentials are invalid or bucket doesn't exist")


def test_configuration():
    """Test configuration settings."""
    print("\n⚙️  Testing Configuration")
    print("-" * 25)
    
    print(f"GCS Bucket Name: {settings.gcs_bucket_name}")
    print(f"GCS Project ID: {settings.gcs_project_id}")
    print(f"Credentials Path: {settings.gcs_credentials_path}")
    print(f"Enable Local Fallback: {settings.enable_local_fallback}")
    print(f"Tmp Directory: {settings.tmp_dir}")
    
    # Test tmp directory creation (should still work for local processing)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    print(f"Tmp directory exists: {settings.tmp_dir.exists()}")


async def main():
    """Run all tests."""
    print("🧪 GCS Storage Integration Tests")
    print("=" * 40)
    
    test_configuration()
    test_path_generation()
    test_error_handling()
    await test_gcs_integration()
    
    print("\n✅ All tests completed!")
    print("\nTo enable GCS storage:")
    print("1. Set GCS_BUCKET_NAME in your .env file")
    print("2. Set up authentication (ADC or service account key)")
    print("3. Ensure the bucket exists in your GCP project")
    print("\nNOTE: Local fallback is now DISABLED.")
    print("The server will fail to start if GCS is not properly configured.")


if __name__ == "__main__":
    asyncio.run(main())