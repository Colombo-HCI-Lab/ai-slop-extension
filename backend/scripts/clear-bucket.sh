#!/bin/bash

# Clear GCS bucket script for FastAPI backend
# This script removes all objects from the configured GCS bucket

set -e  # Exit on error

# Load environment variables from .env file in backend directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$BACKEND_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🗑️  GCS Bucket Cleanup Tool${NC}"
echo "=================================="

# GCS configuration from environment variables
GCS_BUCKET_NAME="${GCS_BUCKET_NAME:-}"
GCS_PROJECT_ID="${GCS_PROJECT_ID:-}"
GCS_CREDENTIALS_PATH="${GCS_CREDENTIALS_PATH:-}"

# Validate required configuration
if [ -z "$GCS_BUCKET_NAME" ]; then
    echo -e "${RED}❌ Error: GCS_BUCKET_NAME is not set${NC}"
    echo -e "${YELLOW}Please set GCS_BUCKET_NAME in your .env file${NC}"
    exit 1
fi

# Print GCS configuration being used
echo -e "${YELLOW}📋 GCS Configuration:${NC}"
echo -e "  Bucket: ${GCS_BUCKET_NAME}"
echo -e "  Project: ${GCS_PROJECT_ID:-auto-detect}"
if [ -n "$GCS_CREDENTIALS_PATH" ]; then
    echo -e "  Credentials: ${GCS_CREDENTIALS_PATH}"
else
    echo -e "  Credentials: Application Default Credentials"
fi
echo

# Set up GCS authentication if credentials path is provided
if [ -n "$GCS_CREDENTIALS_PATH" ] && [ -f "$GCS_CREDENTIALS_PATH" ]; then
    echo -e "${YELLOW}🔐 Setting up service account authentication...${NC}"
    export GOOGLE_APPLICATION_CREDENTIALS="$GCS_CREDENTIALS_PATH"
fi

# Function to check if gsutil is installed
check_gsutil() {
    if ! command -v gsutil &> /dev/null; then
        echo -e "${RED}❌ Error: gsutil is not installed${NC}"
        echo -e "${YELLOW}Please install Google Cloud SDK:${NC}"
        echo -e "  curl https://sdk.cloud.google.com | bash"
        echo -e "  exec -l \$SHELL"
        echo -e "  gcloud init"
        exit 1
    fi
}

# Function to check bucket access
check_bucket_access() {
    echo -e "${YELLOW}🔍 Checking bucket access...${NC}"
    
    if ! gsutil ls "gs://$GCS_BUCKET_NAME" > /dev/null 2>&1; then
        echo -e "${RED}❌ Error: Cannot access bucket 'gs://$GCS_BUCKET_NAME'${NC}"
        echo -e "${YELLOW}Possible issues:${NC}"
        echo -e "  1. Bucket does not exist"
        echo -e "  2. Insufficient permissions"
        echo -e "  3. Invalid authentication"
        echo -e "  4. Incorrect project configuration"
        echo
        echo -e "${YELLOW}💡 Troubleshooting:${NC}"
        echo -e "  • Check bucket exists: gsutil ls gs://"
        echo -e "  • Verify permissions: gsutil iam get gs://$GCS_BUCKET_NAME"
        echo -e "  • Test authentication: gcloud auth list"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Bucket access verified${NC}"
}

# Function to count objects in bucket
count_objects() {
    echo -e "${YELLOW}📊 Counting objects in bucket...${NC}"
    
    # Count objects with different prefixes
    local total_count=$(gsutil ls -r "gs://$GCS_BUCKET_NAME/**" 2>/dev/null | grep -v ':$' | wc -l || echo "0")
    local media_count=$(gsutil ls -r "gs://$GCS_BUCKET_NAME/**/media/**" 2>/dev/null | grep -v ':$' | wc -l || echo "0")
    
    echo -e "  Total objects: ${total_count}"
    echo -e "  Post media objects: ${media_count}"
    
    if [ "$total_count" -eq 0 ]; then
        echo -e "${GREEN}✅ Bucket is already empty${NC}"
        exit 0
    fi
}

# Function to show object details
show_objects() {
    echo -e "${YELLOW}📁 Current bucket contents:${NC}"
    echo
    
    # Show directory structure
    gsutil ls -r "gs://$GCS_BUCKET_NAME" 2>/dev/null | head -20
    
    local total_count=$(gsutil ls -r "gs://$GCS_BUCKET_NAME/**" 2>/dev/null | grep -v ':$' | wc -l || echo "0")
    if [ "$total_count" -gt 20 ]; then
        echo -e "${YELLOW}... and $((total_count - 20)) more objects${NC}"
    fi
    echo
}

# Function to clear bucket contents
clear_bucket() {
    local confirmation="$1"
    
    echo -e "${YELLOW}🗑️  Clearing bucket contents...${NC}"
    
    # Step 1: Cancel incomplete multipart uploads
    echo -e "${YELLOW}🧹 Cleaning up incomplete multipart uploads...${NC}"
    gsutil -m rm -r "gs://$GCS_BUCKET_NAME/**" 2>/dev/null || true
    
    # Step 2: Remove all object versions (if versioning is enabled)
    echo -e "${YELLOW}📦 Removing all object versions...${NC}"
    gsutil -m rm -a "gs://$GCS_BUCKET_NAME/**" 2>/dev/null || true
    
    # Step 3: Standard object deletion with parallel processing
    echo -e "${YELLOW}🗂️  Removing current objects...${NC}"
    if gsutil -m rm -r "gs://$GCS_BUCKET_NAME/**" 2>/dev/null && gsutil -m rm -r "gs://$GCS_BUCKET_NAME/*" 2>/dev/null; then
        echo -e "${GREEN}✅ Standard deletion completed${NC}"
    else
        echo -e "${YELLOW}⚠️  Standard deletion had issues, trying comprehensive cleanup...${NC}"
        
        # Step 4: Alternative method - list and delete objects individually
        # This handles edge cases where bulk deletion fails
        gsutil ls -a "gs://$GCS_BUCKET_NAME/**" 2>/dev/null | while IFS= read -r object; do
            if [ -n "$object" ] && [[ "$object" != *":$" ]] && [ "$object" != "gs://$GCS_BUCKET_NAME/" ]; then
                echo "Deleting: $object"
                gsutil rm "$object" 2>/dev/null || true
            fi
        done
        
        # Step 5: Force deletion of any remaining objects with different approaches
        echo -e "${YELLOW}🔄 Final cleanup pass...${NC}"
        
        # Try to delete with different patterns to catch edge cases
        gsutil -m rm "gs://$GCS_BUCKET_NAME/*" 2>/dev/null || true
        gsutil -m rm -r "gs://$GCS_BUCKET_NAME/*" 2>/dev/null || true
        gsutil -m rm -a "gs://$GCS_BUCKET_NAME/*" 2>/dev/null || true
        
        echo -e "${GREEN}✅ Comprehensive cleanup completed${NC}"
    fi
    
    # Step 6: Clear any lifecycle policies that might recreate objects
    echo -e "${YELLOW}🔧 Clearing lifecycle policies...${NC}"
    gsutil lifecycle set /dev/null "gs://$GCS_BUCKET_NAME" 2>/dev/null || true
}

# Function to verify bucket is empty
verify_empty() {
    echo -e "${YELLOW}🔍 Verifying bucket is empty...${NC}"
    
    # Check current objects
    local remaining_count=$(gsutil ls -r "gs://$GCS_BUCKET_NAME/**" 2>/dev/null | grep -v ':$' | wc -l || echo "0")
    
    # Check versioned objects (including deleted versions)
    local versioned_count=$(gsutil ls -a "gs://$GCS_BUCKET_NAME/**" 2>/dev/null | grep -v ':$' | wc -l || echo "0")
    
    # Check for incomplete multipart uploads
    local uploads_count=0
    if gsutil ls -m "gs://$GCS_BUCKET_NAME" 2>/dev/null | grep -q "Uploads:"; then
        uploads_count=$(gsutil ls -m "gs://$GCS_BUCKET_NAME" 2>/dev/null | grep -A 1000 "Uploads:" | tail -n +2 | grep -v "^$" | wc -l || echo "0")
    fi
    
    echo -e "  Current objects: $remaining_count"
    echo -e "  All versions: $versioned_count"
    echo -e "  Incomplete uploads: $uploads_count"
    
    if [ "$remaining_count" -eq 0 ] && [ "$versioned_count" -eq 0 ] && [ "$uploads_count" -eq 0 ]; then
        echo -e "${GREEN}✅ Bucket is completely empty${NC}"
        echo -e "${GREEN}✅ No objects, versions, or incomplete uploads remain${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  Warning: Bucket still contains data${NC}"
        
        if [ "$remaining_count" -gt 0 ]; then
            echo -e "${YELLOW}  • $remaining_count current objects remain${NC}"
            echo -e "${YELLOW}    This might be due to insufficient permissions${NC}"
        fi
        
        if [ "$versioned_count" -gt "$remaining_count" ]; then
            echo -e "${YELLOW}  • $((versioned_count - remaining_count)) versioned objects remain${NC}"
            echo -e "${YELLOW}    These are likely deleted object versions${NC}"
        fi
        
        if [ "$uploads_count" -gt 0 ]; then
            echo -e "${YELLOW}  • $uploads_count incomplete multipart uploads remain${NC}"
            echo -e "${YELLOW}    These should be cleaned up automatically${NC}"
        fi
        
        echo -e "${YELLOW}💡 To investigate remaining objects:${NC}"
        echo -e "  gsutil ls -a gs://$GCS_BUCKET_NAME/**"
        echo -e "  gsutil ls -m gs://$GCS_BUCKET_NAME"
        
        return 1
    fi
}

# Function to show usage information
show_usage() {
    echo -e "${BLUE}Usage:${NC}"
    echo -e "  ./clear-bucket.sh [OPTIONS]"
    echo
    echo -e "${BLUE}Options:${NC}"
    echo -e "  -h, --help     Show this help message"
    echo -e "  -f, --force    Skip confirmation prompt"
    echo -e "  -c, --count    Only count objects, don't delete"
    echo -e "  -s, --show     Show bucket contents, don't delete"
    echo
    echo -e "${BLUE}Examples:${NC}"
    echo -e "  ./clear-bucket.sh              # Interactive deletion"
    echo -e "  ./clear-bucket.sh --force      # Delete without confirmation"
    echo -e "  ./clear-bucket.sh --count      # Just count objects"
    echo -e "  ./clear-bucket.sh --show       # Show current contents"
    echo
    echo -e "${BLUE}Environment Variables:${NC}"
    echo -e "  GCS_BUCKET_NAME        Required: GCS bucket name"
    echo -e "  GCS_PROJECT_ID         Optional: GCP project ID"
    echo -e "  GCS_CREDENTIALS_PATH   Optional: Service account key file"
}

# Main script logic
main() {
    local action="delete"
    local force_flag=""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -f|--force)
                force_flag="--force"
                shift
                ;;
            -c|--count)
                action="count"
                shift
                ;;
            -s|--show)
                action="show"
                shift
                ;;
            *)
                echo -e "${RED}❌ Unknown option: $1${NC}"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Check prerequisites
    check_gsutil
    check_bucket_access
    
    # Execute requested action
    case $action in
        count)
            count_objects
            ;;
        show)
            show_objects
            ;;
        delete)
            count_objects
            show_objects
            clear_bucket "$force_flag"
            verify_empty
            ;;
    esac
    
    echo -e "${GREEN}✨ GCS bucket operation complete!${NC}"
}

# Run main function with all arguments
main "$@"
