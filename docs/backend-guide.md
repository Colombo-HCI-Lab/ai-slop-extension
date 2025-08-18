# Backend Development Guide

## Overview

The FastAPI backend provides comprehensive AI content detection capabilities across multiple formats (text, images, videos) with Google Gemini-powered chat, database persistence, and real-time processing.

## Features

### Core Detection Capabilities
- **📝 Text Detection**: AI-generated text analysis with pattern recognition
- **🖼️ Image Detection**: ClipBased models with CLIP architecture  
- **🎥 Video Detection**: SlowFast temporal analysis models
- **💬 AI Chat**: Google Gemini integration for discussing results
- **💾 Database Persistence**: PostgreSQL with full CRUD operations

### Technical Features
- **REST API**: Comprehensive FastAPI-based endpoints
- **Database Integration**: SQLAlchemy with Alembic migrations
- **Caching Layer**: Intelligent result caching for performance
- **Batch Processing**: Multiple content analysis support
- **Multi-Model Support**: Various detection algorithms
- **Real-time Chat**: Context-aware conversations about analysis

## Requirements

- Python 3.10+
- PostgreSQL database
- CUDA-capable GPU (optional, CPU fallback)
- Google Gemini API key (for chat features)
- 4GB+ free disk space for models

## API Endpoints

### Text Content Detection
- `POST /api/v1/detect/analyze` - Analyze text content for AI patterns
- `GET /api/v1/detect/cache/stats` - Get detection cache statistics

### Chat & Conversations  
- `POST /api/v1/chat/send` - Send message about a post analysis
- `GET /api/v1/chat/history/{post_id}` - Get conversation history
- `GET /api/v1/chat/suggestions/{post_id}` - Get suggested questions

### Post Management
- `GET /api/v1/posts/{post_id}` - Get specific post details
- `GET /api/v1/posts` - List posts with filtering options
- `PUT /api/v1/posts/{post_id}` - Update post analysis
- `DELETE /api/v1/posts/{post_id}` - Remove post and chat history

### Image Detection
- `POST /api/v1/image/detect` - Upload and analyze image
- `POST /api/v1/image/detect-url` - Analyze image from URL
- `GET /api/v1/image/models` - List available image models

### Video Detection
- `POST /api/v1/detect/video` - Upload and analyze video
- `GET /api/v1/video/models` - List available video models

### System
- `GET /api/v1/health` - Health check and system status
- `GET /docs` - Interactive API documentation (development)

## Database Management

### Migration Scripts

#### `migrate.sh` - Primary Migration Tool
**Usage**: `./migrate.sh [command] [options]`

**Commands**:
- `status` - Show current migration status (default)
- `upgrade` - Apply all pending migrations  
- `downgrade` - Rollback last migration
- `history` - Show migration history
- `create "message"` - Create new migration
- `heads` - Show current head revisions
- `clean` - Remove all migration files (dangerous!)
- `help` - Show help message

**Examples**:
```bash
./migrate.sh status                           # Check current state
./migrate.sh upgrade                          # Apply migrations
./migrate.sh create "Add user preferences"   # Create migration
./migrate.sh downgrade                        # Rollback last migration
./migrate.sh history                          # View history
```

#### `reset-schema.sh` - Full Database Reset
**⚠️ WARNING: This destroys all data!**

```bash
./reset-schema.sh
```

This script will:
1. Terminate all database connections
2. Drop the existing database  
3. Create a new empty database
4. Apply all migrations from scratch

### Manual Database Commands (Advanced)
```bash
# Alembic operations (if scripts don't work)
uv run alembic upgrade head                    # Apply migrations
uv run alembic revision --autogenerate -m "msg"  # Create migration
uv run alembic current                         # Show current state
uv run alembic history                         # Show migration history
uv run alembic downgrade -1                   # Rollback one migration
```

### Database Troubleshooting

#### Connection Issues
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection manually
psql -h localhost -U postgres -d ai_slop_extension

# Verify credentials in .env file
cat .env | grep DATABASE_URL
```

#### Migration Conflicts
```bash
# Check current status
./migrate.sh status

# View detailed history  
./migrate.sh history

# Nuclear option - reset everything
./reset-schema.sh
```

#### Permission Issues
```bash
# Make scripts executable
chmod +x migrate.sh reset-schema.sh
```

### Database Best Practices

1. **Always backup** before running `reset-schema.sh`
2. **Review migrations** before applying with `./migrate.sh status`
3. **Use descriptive messages** when creating migrations
4. **Test migrations** in development before production
5. **Keep migration files** in version control

## Usage Examples

### Text Content Analysis
```bash
# Analyze text content
curl -X POST "http://localhost:4000/api/v1/detect/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "post_id": "123456", 
    "content": "In conclusion, this cutting-edge solution leverages...",
    "author": "John Doe"
  }'
```

### Chat About Analysis
```bash
# Ask questions about detected content
curl -X POST "http://localhost:4000/api/v1/chat/send" \
  -H "Content-Type: application/json" \
  -d '{
    "post_id": "123456",
    "message": "Why was this detected as AI-generated?"
  }'

# Get conversation history
curl "http://localhost:4000/api/v1/chat/history/123456"
```

### Post Management
```bash
# Get specific post
curl "http://localhost:4000/api/v1/posts/123456"

# List posts with filters
curl "http://localhost:4000/api/v1/posts?verdict=ai_slop&limit=10"

# Update post analysis
curl -X PUT "http://localhost:4000/api/v1/posts/123456" \
  -H "Content-Type: application/json" \
  -d '{"confidence": 0.95, "explanation": "Updated analysis"}'
```

### Image & Video Detection
```bash
# Analyze image
curl -X POST "http://localhost:4000/api/v1/image/detect" \
  -F "file=@image.jpg" \
  -F "model_name=clipbased"

# Analyze video  
curl -X POST "http://localhost:4000/api/v1/detect/video" \
  -F "file=@video.mp4" \
  -F "model_name=slowfast_r50"
```

## Testing

### Comprehensive Test Suite
```bash
# Test all migrated functionality
uv run python test_migration.py

# Test video detection system
python test_slowfast.py
python test_slowfast.py --quick    # Skip sample video

# Test image detection system  
python test_clipbased.py
python test_clipbased.py --quick   # Skip weights check

# Run all tests
uv run python test_migration.py && \
  python test_slowfast.py && \
  python test_clipbased.py
```

### CLI Detection (Development)
```bash
# Video analysis
python detect_video.py --demo-hub sample.mp4
python detect_video.py --model slowfast_r101 --threshold 0.6 video.mp4

# Create test content
python detect_video.py --create-test-video sample.mp4
```

## Configuration

### Environment Variables (.env)
```bash
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/ai_slop_extension

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key

# JWT (for future auth)
JWT_SECRET=your-secret-key
JWT_EXPIRATION_DAYS=7

# Server Settings
DEBUG=true
HOST=0.0.0.0
PORT=4000
LOG_LEVEL=INFO

# Model Settings  
DEVICE=auto              # auto, cpu, cuda
DEFAULT_MODEL=slowfast_r50
DEFAULT_IMAGE_MODEL=clipbased

# Cache Settings
REDIS_URL=redis://localhost:6379/0
CACHE_TTL=3600
ENABLE_CACHE=true
```

## Architecture

### Project Structure
```
backend/
├── api/v1/endpoints/          # API route handlers
├── models/                    # SQLAlchemy database models  
├── services/                  # Business logic layer
├── schemas/                   # Pydantic request/response models
├── db/migrations/             # Alembic database migrations
├── core/                      # Configuration and dependencies
├── clipbased_detection/       # Image detection package
├── slowfast_detection/        # Video detection package
├── utils/                     # Utility functions
└── tests/                     # Test files
```

### Key Components
- **Text Detection Service**: Pattern-based AI text analysis
- **Chat Service**: Google Gemini integration with context
- **Database Layer**: SQLAlchemy models with relationships
- **Caching Service**: Performance optimization layer
- **Migration System**: Database schema version control

## Database Schema

### Core Tables

#### `post` table - Analyzed Content Posts
- `id` (UUID) - Primary key
- `post_id` (String) - Facebook post ID (unique)
- `content` (Text) - Post content  
- `author` (String) - Post author
- `verdict` (String) - AI detection result ('ai_slop', 'human_content', 'uncertain')
- `confidence` (Float) - Confidence score (0.0-1.0)
- `explanation` (Text) - Verdict explanation
- `post_metadata` (JSON) - Additional metadata
- `created_at`, `updated_at` (DateTime) - Timestamps
- **Relationships**: One-to-many with chat messages

#### `chat` table - Chat Conversations  
- `id` (UUID) - Primary key
- `post_db_id` (String) - Foreign key to post.id
- `role` (String) - 'user' or 'assistant'
- `message` (Text) - Chat message content
- `created_at`, `updated_at` (DateTime) - Timestamps
- **Relationships**: Many-to-one with posts

## Migration from NestJS

This backend replaces the previous NestJS implementation with enhanced capabilities:

✅ **Migrated Features:**
- Text content AI detection with database persistence
- Google Gemini chat integration with conversation history  
- Post management with full CRUD operations
- Caching layer for improved performance
- Comprehensive API endpoints matching previous functionality

✅ **Enhanced Features:**
- Added video and image detection capabilities
- Improved database schema with proper relationships
- Better error handling and logging
- Comprehensive test coverage
- Database migration system

## Performance Considerations

- **Database Indexes**: `post_id` column is indexed for fast lookups
- **Unique Constraints**: Prevents duplicate posts in database
- **Foreign Key Optimization**: Chat queries can efficiently join with posts
- **Cache Strategy**: Post ID-based caching reduces redundant processing
- **Async Operations**: All database operations are asynchronous
- **Connection Pooling**: SQLAlchemy manages database connections efficiently