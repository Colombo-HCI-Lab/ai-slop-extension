#!/bin/bash

# Chrome Web Store Upload Script
# This script builds and uploads the extension to Chrome Web Store

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_error ".env file not found. Please create one based on .env.example"
    exit 1
fi

# Load environment variables
source .env

# Validate required environment variables
if [ -z "$CHROME_EXTENSION_ID" ] || [ -z "$CHROME_CLIENT_ID" ] || [ -z "$CHROME_CLIENT_SECRET" ]; then
    print_error "Missing required environment variables. Please check your .env file."
    print_error "Required: CHROME_EXTENSION_ID, CHROME_CLIENT_ID, CHROME_CLIENT_SECRET"
    exit 1
fi

# Check if chrome-webstore-upload-cli is installed
if ! command -v npx chrome-webstore-upload-cli &> /dev/null; then
    print_error "chrome-webstore-upload-cli not found. Installing..."
    npm install
fi

print_status "Starting Chrome Web Store upload process..."

# Build the extension
print_status "Building extension..."
npm run build

if [ $? -ne 0 ]; then
    print_error "Build failed. Please fix the build errors before uploading."
    exit 1
fi

# Check if dist directory exists and has files
if [ ! -d "dist" ] || [ -z "$(ls -A dist)" ]; then
    print_error "Build output directory 'dist' is empty or doesn't exist."
    exit 1
fi

print_status "Build completed successfully."

# Create zip file for upload
print_status "Creating extension package..."
cd dist
zip -r ../extension.zip . -x "*.DS_Store" "*.map"
cd ..

if [ ! -f "extension.zip" ]; then
    print_error "Failed to create extension.zip"
    exit 1
fi

print_status "Extension package created: extension.zip"

# Get refresh token if not exists
REFRESH_TOKEN_FILE=".refresh_token"
if [ ! -f "$REFRESH_TOKEN_FILE" ]; then
    print_warning "Refresh token not found. Starting OAuth authentication flow..."
    
    # Choose an available port
    PORT=8080
    REDIRECT_URI="http://localhost:$PORT"
    
    # Check if OAuth server file exists
    if [ ! -f "oauth_server.js" ]; then
        print_error "oauth_server.js not found. Please ensure it's in the same directory as this script."
        exit 1
    fi

    # Start the OAuth callback server in background
    print_status "Starting OAuth callback server on port $PORT..."
    node oauth_server.js $PORT > oauth_output.txt 2>&1 &
    SERVER_PID=$!
    
    # Wait a moment for server to start
    sleep 2
    
    # Create OAuth URL with prompt=consent to force refresh token
    OAUTH_URL="https://accounts.google.com/o/oauth2/auth?response_type=code&scope=https://www.googleapis.com/auth/chromewebstore&client_id=$CHROME_CLIENT_ID&redirect_uri=$REDIRECT_URI&access_type=offline&prompt=consent"
    
    print_status "Opening browser for authentication..."
    echo "OAuth URL: $OAUTH_URL"
    
    # Try to open browser automatically
    if command -v open &> /dev/null; then
        open "$OAUTH_URL"
    elif command -v xdg-open &> /dev/null; then
        xdg-open "$OAUTH_URL"
    elif command -v start &> /dev/null; then
        start "$OAUTH_URL"
    else
        print_warning "Could not open browser automatically. Please open this URL manually:"
        echo "$OAUTH_URL"
    fi
    
    print_status "Waiting for authentication to complete in browser..."
    print_status "The browser will redirect to localhost:$PORT to capture the authorization code."
    
    # Wait for the server process to complete
    wait $SERVER_PID
    SERVER_EXIT_CODE=$?
    
    # Read the authorization code from output
    if [ $SERVER_EXIT_CODE -eq 0 ] && [ -f oauth_output.txt ]; then
        AUTH_CODE=$(tail -n 1 oauth_output.txt | grep -v "OAuth callback server listening")
        AUTH_CODE=$(echo "$AUTH_CODE" | tr -d '\n\r')
    fi
    
    # Cleanup temporary files
    rm -f oauth_output.txt
    
    if [ -z "$AUTH_CODE" ]; then
        print_error "Failed to get authorization code. Please try again."
        exit 1
    fi
    
    print_status "Authorization code received successfully!"
    
    # Exchange authorization code for refresh token
    print_status "Exchanging authorization code for refresh token..."
    RESPONSE=$(curl -s -d "client_id=$CHROME_CLIENT_ID&client_secret=$CHROME_CLIENT_SECRET&code=$AUTH_CODE&grant_type=authorization_code&redirect_uri=$REDIRECT_URI" https://accounts.google.com/o/oauth2/token)
    
    # Extract refresh token from response using multiple methods
    REFRESH_TOKEN=""
    
    # Method 1: Python JSON parsing (most reliable)
    if command -v python3 &> /dev/null; then
        REFRESH_TOKEN=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('refresh_token', ''))
except:
    pass
" 2>/dev/null)
    fi
    
    # Method 2: Node.js JSON parsing (fallback)
    if [ -z "$REFRESH_TOKEN" ] && command -v node &> /dev/null; then
        REFRESH_TOKEN=$(echo "$RESPONSE" | node -e "
try {
    const data = JSON.parse(require('fs').readFileSync(0, 'utf8'));
    console.log(data.refresh_token || '');
} catch(e) {}
" 2>/dev/null)
    fi
    
    # Method 3: Regex fallback
    if [ -z "$REFRESH_TOKEN" ]; then
        REFRESH_TOKEN=$(echo "$RESPONSE" | sed -n 's/.*"refresh_token": *"\([^"]*\)".*/\1/p')
    fi
    
    if [ -z "$REFRESH_TOKEN" ]; then
        print_error "No refresh token in response. This usually means:"
        print_error "1. You've already authorized this app before"
        print_error "2. Try revoking app permissions at: https://myaccount.google.com/permissions"
        print_error "3. Then run the script again"
        echo ""
        print_error "Response received:"
        echo "$RESPONSE"
        exit 1
    fi
    
    # Save refresh token to file
    echo "$REFRESH_TOKEN" > "$REFRESH_TOKEN_FILE"
    print_status "Refresh token saved to $REFRESH_TOKEN_FILE"
else
    # Read refresh token from file
    REFRESH_TOKEN=$(cat "$REFRESH_TOKEN_FILE")
    
    if [ -z "$REFRESH_TOKEN" ]; then
        print_error "Invalid refresh token in $REFRESH_TOKEN_FILE. Please delete the file and try again."
        exit 1
    fi
fi

# Upload to Chrome Web Store
print_status "Uploading extension to Chrome Web Store..."

npx chrome-webstore-upload-cli upload \
    --source="extension.zip" \
    --extension-id="$CHROME_EXTENSION_ID" \
    --client-id="$CHROME_CLIENT_ID" \
    --client-secret="$CHROME_CLIENT_SECRET" \
    --refresh-token="$REFRESH_TOKEN" \
    --auto-publish

if [ $? -eq 0 ]; then
    print_status "Extension uploaded and published successfully!"
    print_status "You can view your extension at: https://chrome.google.com/webstore/detail/$CHROME_EXTENSION_ID"
else
    print_error "Upload failed. Please check the error messages above."
    exit 1
fi

# Cleanup
print_status "Cleaning up temporary files..."
rm -f extension.zip

print_status "Upload process completed!"