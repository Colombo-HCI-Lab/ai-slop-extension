# AI Slop Detection

Browser extension for detecting AI-generated content on Facebook with real-time analysis and intelligent chat.

## Installation

### Option 1: Download from Releases (Recommended)
1. Go to [Releases](../../releases) and download `ai-slop-extension.zip`
2. Extract the ZIP file to a folder
3. Open Chrome and go to `chrome://extensions/`
4. Enable "Developer mode" (toggle in top right)
5. Click "Load unpacked" and select the extracted folder

### Option 2: Build from Source
```bash
cd browser-extension
npm install && npm run build
# Load 'dist/' folder in Chrome extensions
```

## Backend Setup (Optional)
For advanced features like chat and analytics:
```bash
cd backend
uv venv --python 3.10 && uv sync
./migrate.sh upgrade
uv run python -m uvicorn main:app --reload --port 4000
```

### Storage
- Temporary media files are saved to a local directory specified by `TMP_DIR`.
- Local development defaults to `tmp/` under `backend/` (configurable via `.env`).
- Deployed environments set `TMP_DIR=/ai-slop-extension/tmp`.
- No Google Cloud Storage or gcsfuse is used.

## Features

- **Multi-format Detection** - Text, images, and videos
- **Real-time Analysis** - Instant feedback while browsing
- **AI Chat** - Google Gemini-powered conversations about results
- **Analytics** - User behavior and interaction tracking
- **Database Persistence** - PostgreSQL with migration system

## Documentation

- **[Documentation Hub](docs/README.md)** - Complete project documentation
- **[Backend Guide](docs/backend-guide.md)** - API setup and development
- **[Extension Guide](docs/extension-guide.md)** - Chrome extension development
- **[Database Schema](docs/database-schema.md)** - Database design and relationships

## Project Structure

```
ai-slop-extension/
├── backend/                 # FastAPI backend
├── browser-extension/       # Chrome extension
├── docs/                   # Project documentation
└── README.md               # This file
```
