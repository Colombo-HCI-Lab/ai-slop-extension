#!/usr/bin/env python3
"""
Test script for yt-dlp integration with Facebook video downloading.
"""

import asyncio

from services.ytdlp_video_service import YtDlpVideoService
from utils.logging import setup_logging, get_logger

# Initialize logging
setup_logging()
logger = get_logger(__name__)


async def test_ytdlp_service():
    """Test the YtDlpVideoService with a public Facebook video."""

    # Initialize service
    service = YtDlpVideoService()

    # Test with a hypothetical Facebook post URL (user should provide real URL)
    test_post_url = "https://www.facebook.com/watch/?v=123456789"  # Replace with real URL
    test_post_id = "test_post_123"

    print("🧪 Testing yt-dlp integration")
    print(f"📊 Service: {type(service).__name__}")
    print(f"🆔 Test post ID: {test_post_id}")
    print(f"🔗 Test URL: {test_post_url[:50]}...")

    try:
        # Test 1: Extract video info without downloading
        print("\n📋 Test 1: Extracting video info...")
        info = await service.extract_video_info(test_post_url)

        if info:
            print("✅ Video info extraction successful:")
            print(f"   Title: {info.get('title', 'N/A')[:50]}")
            print(f"   Duration: {info.get('duration', 'N/A')} seconds")
            print(f"   Format: {info.get('ext', 'N/A')}")
        else:
            print("❌ Failed to extract video info")
            print("💡 This might be because the URL is private or doesn't exist")

        # Test 2: Download video (only if info extraction worked)
        if info:
            print("\n📥 Test 2: Downloading video...")
            video_path = await service.download_facebook_video(test_post_url, test_post_id, video_index=0)

            if video_path and video_path.exists():
                file_size = video_path.stat().st_size
                print(f"✅ Video downloaded successfully:")
                print(f"   Path: {video_path}")
                print(f"   Size: {file_size / (1024 * 1024):.2f} MB")
            else:
                print("❌ Video download failed")

        # Test 3: Test with retry mechanism
        print("\n🔄 Test 3: Testing retry mechanism...")
        retry_result = await service.download_with_retry(test_post_url, test_post_id + "_retry", max_retries=2)

        if retry_result:
            print(f"✅ Retry download successful: {retry_result}")
        else:
            print("❌ Retry download failed")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        logger.error("Test error", error=str(e), exc_info=True)


async def test_ytdlp_command():
    """Test yt-dlp command line tool directly."""

    print("\n🔧 Testing yt-dlp command line tool...")

    import subprocess

    try:
        # Test yt-dlp version
        result = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ yt-dlp version: {result.stdout.strip()}")
        else:
            print(f"❌ yt-dlp not working: {result.stderr}")

        # Test supported extractors
        result = subprocess.run(["yt-dlp", "--list-extractors", "facebook"], capture_output=True, text=True)
        if result.returncode == 0 and "facebook" in result.stdout.lower():
            print("✅ Facebook extractor is supported")
        else:
            print("❌ Facebook extractor not found")

    except FileNotFoundError:
        print("❌ yt-dlp command not found in PATH")
    except Exception as e:
        print(f"❌ Command test failed: {e}")


def main():
    """Main test function."""

    print("🚀 Starting yt-dlp Integration Tests")
    print("=" * 50)

    # Run async tests
    asyncio.run(test_ytdlp_command())

    # Note about Facebook URLs
    print("\n📝 Note about testing with real Facebook URLs:")
    print("   - Replace test_post_url with a real Facebook video URL")
    print("   - Public videos work best for testing")
    print("   - Private videos may require authentication")
    print("   - Some videos might be region-restricted")

    # Show service configuration
    service = YtDlpVideoService()
    print(f"\n⚙️  Service Configuration:")
    print(f"   Output directory: {service.base_output_dir}")
    print(f"   User agent: {service.base_ydl_opts.get('user_agent', 'N/A')[:50]}...")

    # Run service test with warning
    print("\n⚠️  To test with a real Facebook URL, update test_post_url in the script")
    print("   and uncomment the line below:")
    print()
    # Uncomment to test with real URL:
    # asyncio.run(test_ytdlp_service())


if __name__ == "__main__":
    main()
