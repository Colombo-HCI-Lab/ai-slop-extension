#!/usr/bin/env python3
"""
Clear GCS bucket script using Python GCS client.
This script removes all objects from the configured GCS bucket.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from services.gcs_storage_service import GCSStorageService
from core.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


def print_colored(message: str, color: str = ""):
    """Print colored message to console."""
    colors = {
        "red": "\033[0;31m",
        "green": "\033[0;32m", 
        "yellow": "\033[1;33m",
        "blue": "\033[0;34m",
        "reset": "\033[0m"
    }
    
    color_code = colors.get(color, "")
    reset_code = colors["reset"]
    print(f"{color_code}{message}{reset_code}")


async def count_objects(gcs_service: GCSStorageService) -> int:
    """Count objects in the bucket."""
    print_colored("📊 Counting objects in bucket...", "yellow")
    
    try:
        # List all blobs in the bucket
        blobs = gcs_service.client.list_blobs(gcs_service.bucket)
        
        total_count = 0
        posts_count = 0
        
        for blob in blobs:
            total_count += 1
            if blob.name.startswith("posts/"):
                posts_count += 1
        
        print(f"  Total objects: {total_count}")
        print(f"  Posts objects: {posts_count}")
        
        if total_count == 0:
            print_colored("✅ Bucket is already empty", "green")
        
        return total_count
        
    except Exception as e:
        print_colored(f"❌ Error counting objects: {str(e)}", "red")
        return 0


async def show_objects(gcs_service: GCSStorageService, limit: int = 20):
    """Show objects in the bucket."""
    print_colored("📁 Current bucket contents:", "yellow")
    print()
    
    try:
        # List all blobs in the bucket
        blobs = gcs_service.client.list_blobs(gcs_service.bucket)
        
        count = 0
        for blob in blobs:
            if count >= limit:
                print_colored(f"... and more objects (showing first {limit})", "yellow")
                break
            
            # Show object name, size, and creation time
            size_mb = blob.size / (1024 * 1024) if blob.size else 0
            created = blob.time_created.strftime("%Y-%m-%d %H:%M:%S") if blob.time_created else "unknown"
            print(f"  gs://{settings.gcs_bucket_name}/{blob.name}")
            print(f"    Size: {size_mb:.2f} MB, Created: {created}")
            count += 1
        
        print()
        
    except Exception as e:
        print_colored(f"❌ Error listing objects: {str(e)}", "red")


async def clear_bucket(gcs_service: GCSStorageService, force: bool = False):
    """Clear all objects from the bucket."""
    # Count objects first
    total_count = await count_objects(gcs_service)
    
    if total_count == 0:
        return
    
    if not force:
        print_colored("⚠️  WARNING: This will permanently delete ALL objects in the bucket!", "red")
        print_colored(f"Bucket: gs://{settings.gcs_bucket_name}", "yellow")
        print()
        
        confirmation = input("Are you sure you want to continue? (yes/no): ")
        if confirmation.lower() != "yes":
            print_colored("❌ Operation cancelled", "yellow")
            return
    
    print_colored("🗑️  Clearing bucket contents...", "yellow")
    
    try:
        # Delete all objects in the bucket
        blobs = gcs_service.client.list_blobs(gcs_service.bucket)
        
        deleted_count = 0
        for blob in blobs:
            try:
                blob.delete()
                deleted_count += 1
                if deleted_count % 10 == 0:  # Progress indicator
                    print(f"  Deleted {deleted_count} objects...")
            except Exception as e:
                print_colored(f"⚠️  Failed to delete {blob.name}: {str(e)}", "yellow")
        
        print_colored(f"✅ Successfully deleted {deleted_count} objects", "green")
        
        # Verify bucket is empty
        remaining_count = await count_objects(gcs_service)
        if remaining_count == 0:
            print_colored("✅ Bucket is now empty", "green")
        else:
            print_colored(f"⚠️  Warning: {remaining_count} objects still remain", "yellow")
        
    except Exception as e:
        print_colored(f"❌ Error clearing bucket: {str(e)}", "red")
        sys.exit(1)


def show_configuration():
    """Show current GCS configuration."""
    print_colored("📋 GCS Configuration:", "yellow")
    print(f"  Bucket: {settings.gcs_bucket_name}")
    print(f"  Project: {settings.gcs_project_id or 'auto-detect'}")
    if settings.gcs_credentials_path:
        print(f"  Credentials: {settings.gcs_credentials_path}")
    else:
        print("  Credentials: Application Default Credentials")
    print()


async def main():
    """Main script function."""
    parser = argparse.ArgumentParser(
        description="Clear GCS bucket contents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python clear_bucket.py              # Interactive deletion
  python clear_bucket.py --force      # Delete without confirmation  
  python clear_bucket.py --count      # Just count objects
  python clear_bucket.py --show       # Show current contents

Environment Variables:
  GCS_BUCKET_NAME        Required: GCS bucket name
  GCS_PROJECT_ID         Optional: GCP project ID  
  GCS_CREDENTIALS_PATH   Optional: Service account key file
        """
    )
    
    parser.add_argument(
        "-f", "--force", 
        action="store_true",
        help="Skip confirmation prompt"
    )
    parser.add_argument(
        "-c", "--count",
        action="store_true", 
        help="Only count objects, don't delete"
    )
    parser.add_argument(
        "-s", "--show",
        action="store_true",
        help="Show bucket contents, don't delete"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Limit number of objects to show (default: 20)"
    )
    
    args = parser.parse_args()
    
    print_colored("🗑️  GCS Bucket Cleanup Tool", "blue")
    print("==================================")
    
    # Show configuration
    show_configuration()
    
    # Validate configuration
    if not settings.gcs_bucket_name:
        print_colored("❌ Error: GCS_BUCKET_NAME is not set", "red")
        print_colored("Please set GCS_BUCKET_NAME in your .env file", "yellow")
        sys.exit(1)
    
    # Initialize GCS service
    try:
        print_colored("🔍 Initializing GCS service...", "yellow")
        gcs_service = GCSStorageService()
        print_colored("✅ GCS service initialized successfully", "green")
    except Exception as e:
        print_colored(f"❌ Error initializing GCS service: {str(e)}", "red")
        print_colored("💡 Check your GCS configuration and credentials", "yellow")
        sys.exit(1)
    
    # Execute requested action
    try:
        if args.count:
            await count_objects(gcs_service)
        elif args.show:
            await show_objects(gcs_service, args.limit)
        else:
            # Default: clear bucket
            await show_objects(gcs_service, args.limit)
            await clear_bucket(gcs_service, args.force)
            
    except KeyboardInterrupt:
        print_colored("\n❌ Operation cancelled by user", "yellow")
        sys.exit(1)
    except Exception as e:
        print_colored(f"❌ Unexpected error: {str(e)}", "red")
        sys.exit(1)
    
    print_colored("✨ GCS bucket operation complete!", "green")


if __name__ == "__main__":
    asyncio.run(main())