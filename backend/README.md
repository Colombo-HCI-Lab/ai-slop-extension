# Backend

FastAPI backend for AI content detection (text, images, videos) with chat and database features.

## Quick Setup

```bash
# Install dependencies
uv venv --python 3.10
uv sync

# Setup database
./migrate.sh upgrade

# Start development server
uv run python -m uvicorn main:app --reload --port 4000
```

## Environment

Copy `.env` example and configure:
```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/ai_slop_extension
GEMINI_API_KEY=your_gemini_api_key
PORT=4000
DEBUG=true
```

## Test

```bash
uv run python test_migration.py
```

## Documentation

- **[Backend Guide](../docs/backend-guide.md)** - Complete setup, API, and development guide
- **[Database Schema](../docs/database-schema.md)** - Database design and relationships
- **[Migration Plan](MIGRATION_PLAN.md)** - NestJS to FastAPI migration details