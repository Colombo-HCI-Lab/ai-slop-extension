# Facebook Post ID Flow Documentation

## Overview

This document demonstrates how Facebook post IDs are extracted, used, and tracked throughout the AI Slop Detection system, ensuring consistent post identification across all components.

## System Architecture

The post ID flows through these components:
1. **Browser Extension** (Content Script) - Extracts post ID
2. **Browser Extension** (Background Service) - Forwards to backend
3. **Backend API** (Detection Controller) - Processes requests
4. **Backend Services** (Cache & Database) - Stores results
5. **Database** - Persists with relationships
6. **Chat System** - References posts for conversations

## Data Flow Implementation

### 1. Browser Extension Content Script

The content script extracts Facebook's numeric post ID from DOM elements and URLs.

```javascript
// browser-extension/src/content/index.ts:generatePostId()
const postId = await this.generatePostId(postElement);
// Returns: "24312088291761638" (Facebook's numeric post ID)

// Content script sends to background service
chrome.runtime.sendMessage({
  type: 'AI_SLOP_REQUEST',
  content: postContent,
  postId: postId  // "24312088291761638"
});
```

**Post ID Extraction Examples:**
- From URL: `https://www.facebook.com/groups/123/posts/24312088291761638/`
- From DOM: `data-ft` attributes, permalink structures
- From comments: `...posts/24312088291761638/?comment_id=123456`

### 2. Browser Extension Background Service

The background service forwards the post ID along with content to the backend API.

```javascript
// browser-extension/src/background/index.ts:handleAiSlopRequest()
const requestBody = {
  content,
  postId,  // "24312088291761638"
  author: extractedAuthor,
  metadata: {
    url: postUrl,
    timestamp: Date.now()
  }
};

// Sends to backend API
fetch('http://localhost:4000/api/v1/detect/analyze', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(requestBody)
});
```

### 3. Backend API Detection Controller

The FastAPI controller receives and processes the post ID for analysis.

```python
# backend/api/v1/endpoints/detect.py
@router.post("/analyze")
async def analyze_text(request: DetectRequest, db: AsyncSession = Depends(get_db)):
    # request.post_id = "24312088291761638"
    result = await detection_service.detect(request, db)
    return result
```

**Request Schema:**
```python
class DetectRequest(BaseModel):
    post_id: str  # "24312088291761638"
    content: str
    author: Optional[str] = None
    metadata: Optional[dict] = None
```

### 4. Backend Detection Service

The service uses post ID for caching and database operations.

```python
# backend/services/text_detection_service.py
async def detect(self, request: DetectRequest, db: AsyncSession):
    # Check cache using Facebook post ID
    cached_result = await self._get_cached_result(request.post_id, db)
    if cached_result:
        return self._create_response_from_post(cached_result, from_cache=True)
    
    # Perform analysis and save to database
    verdict, confidence, explanation = self._analyze_content(request.content)
    post = await self._save_to_database(request, verdict, confidence, explanation, db)
    
    return self._create_response_from_post(post, from_cache=False)
```

### 5. Database Storage

The database uses Facebook post ID as a unique identifier with proper relationships.

```python
# backend/models/post.py
class Post(Base):
    __tablename__ = "post"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # Internal UUID
    post_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)  # Facebook ID
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verdict: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationship to chat conversations
    chats: Mapped[list["Chat"]] = relationship("Chat", back_populates="post")
```

**Database Operations:**
```python
# Upsert post by Facebook post ID
post = await self._save_to_database(request, verdict, confidence, explanation, db)

# Query by Facebook post ID
existing = await db.execute(
    select(Post).where(Post.post_id == request.post_id)
)
```

### 6. Chat System Integration

Chat conversations reference posts using the Facebook post ID for user-friendly access.

```python
# backend/services/chat_service.py
async def send_message(self, request: ChatRequest, db: AsyncSession):
    # Find post by Facebook post ID
    post = await self._get_post(request.post_id, db)  # "24312088291761638"
    if not post:
        raise ValueError(f"Post with ID {request.post_id} not found")
    
    # Save chat message using internal database ID
    chat = Chat(
        id=str(uuid.uuid4()),
        post_db_id=post.id,  # Internal UUID reference
        role="user",
        message=request.message
    )
    
    db.add(chat)
    await db.commit()
```

## Database Schema Relationships

```sql
-- Post table with Facebook post ID
CREATE TABLE post (
    id VARCHAR(36) PRIMARY KEY,           -- Internal UUID
    post_id VARCHAR(255) UNIQUE NOT NULL, -- Facebook post ID "24312088291761638"
    content TEXT NOT NULL,
    verdict VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL,
    -- ...
);

-- Chat table with foreign key to post
CREATE TABLE chat (
    id VARCHAR(36) PRIMARY KEY,
    post_db_id VARCHAR(36) NOT NULL,      -- References post.id (internal UUID)
    role VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    -- ...
    FOREIGN KEY (post_db_id) REFERENCES post(id) ON DELETE CASCADE
);
```

## Key Benefits

### 1. Consistent Post Identity
- Same Facebook post always has ID `"24312088291761638"`
- Cross-user consistency: multiple users see same analysis
- No duplicate processing for the same post

### 2. Efficient Caching
- Posts analyzed once are cached by Facebook post ID
- Subsequent requests return cached results immediately
- Reduces API calls and processing time

### 3. Proper Database Relations
- Chat messages correctly linked to posts via foreign keys
- Internal UUIDs for database efficiency
- Facebook post IDs for user-facing operations

### 4. Cross-Component Consistency
- Same post ID used from browser extension to database
- Eliminates confusion between different ID formats
- Enables reliable post tracking and analytics

## Post ID Extraction Examples

| Facebook URL | Extracted Post ID | Notes |
|--------------|------------------|-------|
| `https://www.facebook.com/groups/1638417209555402/posts/24312088291761638/` | `24312088291761638` | Standard group post |
| `https://www.facebook.com/groups/1638417209555402/posts/24335126272791173/` | `24335126272791173` | Another group post |
| `https://www.facebook.com/groups/1638417209555402/posts/2489476187782829/` | `2489476187782829` | Shorter post ID |
| `...posts/24312088291761638/?comment_id=123456` | `24312088291761638` | Comment URL |
| `...posts/24312088291761638/?comment_id=789012` | `24312088291761638` | Different comment, same post |

## API Request/Response Flow

### Detection Request
```json
{
  "post_id": "24312088291761638",
  "content": "This is the post content to analyze...",
  "author": "John Doe",
  "metadata": {
    "url": "https://www.facebook.com/groups/.../posts/24312088291761638/",
    "timestamp": 1708875600000
  }
}
```

### Detection Response
```json
{
  "post_id": "24312088291761638",
  "verdict": "ai_slop",
  "confidence": 0.87,
  "explanation": "Detected multiple AI-typical patterns...",
  "timestamp": "2024-02-25T14:20:00Z",
  "debug_info": {
    "mode": "real_detection",
    "from_cache": false
  }
}
```

### Chat Request
```json
{
  "post_id": "24312088291761638",
  "message": "Why was this detected as AI-generated?"
}
```

## Error Handling

- **Invalid Post ID**: Returns 400 Bad Request with validation error
- **Post Not Found**: Returns 404 Not Found for chat requests on non-existent posts
- **Database Errors**: Proper error propagation with logging
- **Cache Misses**: Graceful fallback to fresh analysis

## Performance Considerations

- **Database Indexes**: `post_id` column is indexed for fast lookups
- **Unique Constraints**: Prevents duplicate posts in database
- **Foreign Key Optimization**: Chat queries can efficiently join with posts
- **Cache Strategy**: Post ID-based caching reduces redundant processing