# AI Slop Detection

Browser extension for detecting AI-generated content on Facebook with real-time analysis and intelligent chat.

## Quick Start

### Backend
```bash
cd backend
uv venv --python 3.10 && uv sync
./migrate.sh upgrade
uv run python -m uvicorn main:app --reload --port 4000
```

### Extension
```bash
cd browser-extension
npm install && npm start
# Load 'dist/' folder in Chrome extensions
```

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
