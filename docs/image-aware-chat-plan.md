# Image-Aware Chat System Design for AI Slop Extension

## Overview
Enhance the chat functionality to include image understanding by uploading post images to Gemini and maintaining user-specific chat sessions with proper image context.

## Key Requirements
1. **Image Integration**: Upload post images using Gemini File API for multimodal understanding
2. **User Isolation**: Maintain separate chat sessions per user (not shared across extension users)
3. **Session Management**: Track chat history and uploaded files per user/post combination
4. **Multimodal Context**: Provide Gemini with both text and image content for comprehensive analysis
5. **Media Storage**: Store image and video URLs from posts for project-wide usage

## Architecture Design

### 1. Database Schema Updates
```sql
-- Add user_session table to track individual users
CREATE TABLE user_session (
    id UUID PRIMARY KEY,
    user_identifier VARCHAR(255) UNIQUE NOT NULL,  -- Browser-generated UUID
    created_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP DEFAULT NOW()
);

-- Update chat table to include user context
ALTER TABLE chat 
ADD COLUMN user_session_id UUID REFERENCES user_session(id),
ADD COLUMN file_uris JSONB;  -- Store Gemini file URIs for images

-- Add post_media table for storing image/video URLs
CREATE TABLE post_media (
    id UUID PRIMARY KEY,
    post_db_id UUID REFERENCES post(id) ON DELETE CASCADE,
    media_type VARCHAR(20) NOT NULL,  -- 'image' or 'video'
    media_url TEXT NOT NULL,
    thumbnail_url TEXT,
    width INTEGER,
    height INTEGER,
    file_size BIGINT,
    mime_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Add indexes for efficient queries
CREATE INDEX idx_chat_user_post ON chat(user_session_id, post_db_id);
CREATE INDEX idx_post_media_post ON post_media(post_db_id);
CREATE INDEX idx_post_media_type ON post_media(media_type);
```

### 2. Image Upload Flow

#### 2.1 Browser Extension Changes
```typescript
// Generate/retrieve persistent user identifier
const getUserIdentifier = (): string => {
  let userId = localStorage.getItem('ai-slop-user-id');
  if (!userId) {
    userId = crypto.randomUUID();
    localStorage.setItem('ai-slop-user-id', userId);
  }
  return userId;
};

// Enhanced chat request with images
interface ChatRequest {
  post_id: string;
  message: string;
  user_id: string;
  image_urls?: string[];  // Facebook image URLs from post
}
```

#### 2.2 Backend Service Updates

##### File Upload Service (`services/file_upload_service.py`)
```python
import aiohttp
import google.generativeai as genai
from typing import List, Optional
from utils.logging import get_logger

logger = get_logger(__name__)

class FileUploadService:
    """Handles image uploads to Gemini File API."""
    
    async def upload_images_from_urls(self, image_urls: List[str]) -> List[str]:
        """Download images from URLs and upload to Gemini."""
        file_uris = []
        
        for url in image_urls:
            try:
                # Download image
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            
                            # Upload to Gemini
                            file = genai.upload_file(
                                data=image_data,
                                mime_type=response.headers.get('content-type', 'image/jpeg')
                            )
                            file_uris.append(file.uri)
                            logger.info(f"Uploaded image to Gemini: {file.uri}")
            except Exception as e:
                logger.error(f"Failed to upload image from {url}: {e}")
                
        return file_uris
```

##### Enhanced Chat Service (`services/chat_service.py`)
```python
class ChatService:
    def __init__(self):
        self.file_service = FileUploadService()
        
    async def send_message(
        self,
        request: ChatRequest,
        db: AsyncSession,
    ) -> ChatResponse:
        # Get or create user session
        user_session = await self._get_or_create_user_session(request.user_id, db)
        
        # Get post with user-specific chat history
        post = await self._get_post(request.post_id, db)
        chat_history = await self._get_user_chat_history(
            post.id, user_session.id, db
        )
        
        # Upload images if provided and not already uploaded
        file_uris = []
        if request.image_urls and not chat_history:
            file_uris = await self.file_service.upload_images_from_urls(
                request.image_urls
            )
        elif chat_history and chat_history[0].file_uris:
            # Reuse previously uploaded files
            file_uris = chat_history[0].file_uris
            
        # Save user message with file references
        await self._save_message(
            post.id, 
            user_session.id,
            "user", 
            request.message,
            file_uris,
            db
        )
        
        # Generate response with images
        response_text = await self._generate_multimodal_response(
            post, 
            request.message,
            chat_history,
            file_uris
        )
        
        # Save and return response
        # ... rest of implementation
```

### 3. Multimodal Gemini Integration

```python
async def _generate_multimodal_response(
    self,
    post: Post,
    user_message: str,
    chat_history: List[Chat],
    file_uris: List[str]
) -> str:
    """Generate response using text and images."""
    
    # Build system instruction with image context
    system_instruction = f"""You are an expert AI content detection assistant.
    
POST CONTENT: "{post.content}"
IMAGES: {len(file_uris)} images from the post are provided for analysis

DETECTION RESULTS:
{self._build_detection_summary(post)}

Analyze both the text and images to provide comprehensive insights about:
- Visual indicators of AI generation (unnatural lighting, artifacts, inconsistencies)
- Correlation between text claims and image content
- Overall authenticity assessment combining all modalities
"""
    
    # Initialize model
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        system_instruction=system_instruction
    )
    
    # Create multimodal prompt
    prompt_parts = []
    
    # Add images if available
    for uri in file_uris:
        file = genai.get_file(uri)
        prompt_parts.append(file)
    
    # Add conversation context
    prompt_parts.append(f"User question: {user_message}")
    
    # Generate response
    response = model.generate_content(prompt_parts)
    return response.text
```

### 4. API Endpoint Updates

```python
# schemas/chat.py
class ChatRequest(BaseModel):
    post_id: str
    message: str
    user_id: str = Field(..., description="Unique user identifier")
    image_urls: Optional[List[str]] = Field(None, description="Post image URLs")

# api/v1/endpoints/chat.py
@router.post("/send", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    # Validate user_id format
    if not request.user_id or not is_valid_uuid(request.user_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid user identifier"
        )
    
    response = await chat_service.send_message(request, db)
    return response
```

### 5. Browser Extension Updates

```typescript
// src/content/index.ts
private async sendChatMessage(
  chatWindow: HTMLElement, 
  message: string
): Promise<void> {
  const postId = chatWindow.getAttribute('data-post-id') || '';
  const postImages = this.extractPostImages(postId);
  const userId = getUserIdentifier();
  
  const response = await chrome.runtime.sendMessage({
    type: 'CHAT_REQUEST',
    postId: postId,
    message: message,
    userId: userId,
    imageUrls: postImages,
  });
  
  // Handle response...
}

private extractPostImages(postId: string): string[] {
  const images: string[] = [];
  const postElement = document.querySelector(`[data-post-id="${postId}"]`);
  
  if (postElement) {
    // Extract image URLs from Facebook post
    const imgElements = postElement.querySelectorAll('img[src*="scontent"]');
    imgElements.forEach(img => {
      const src = img.getAttribute('src');
      if (src && !src.includes('emoji')) {
        images.push(src);
      }
    });
  }
  
  return images;
}
```

## Implementation Steps

1. **Phase 1: Database Setup**
   - Create migration for user_session table
   - Update chat table schema
   - Add post_media table
   - Add necessary indexes

2. **Phase 2: Backend Services**
   - Implement FileUploadService
   - Update ChatService with multimodal support
   - Add user session management
   - Add post media management

3. **Phase 3: API Updates**
   - Update request/response schemas
   - Add user_id validation
   - Handle image URLs in requests

4. **Phase 4: Extension Integration**
   - Add user identifier generation
   - Extract images from Facebook posts
   - Update chat API calls

5. **Phase 5: Testing**
   - Test image upload functionality
   - Verify user session isolation
   - Test multimodal responses

## Benefits

1. **Enhanced Analysis**: Gemini can analyze both text and visual content for more accurate detection
2. **User Privacy**: Each user has isolated chat sessions
3. **Persistent Context**: Images uploaded once, reused in conversation
4. **Comprehensive Detection**: Visual artifacts and text-image consistency checks
5. **Media Management**: Centralized storage of post media for project-wide usage

## Security Considerations

1. **User Isolation**: Strict session boundaries prevent data leakage
2. **File Management**: Regular cleanup of old uploaded files
3. **Rate Limiting**: Prevent abuse of image upload API
4. **Privacy**: User identifiers are anonymous UUIDs

## Performance Optimizations

1. **File Caching**: Reuse uploaded files within same session
2. **Lazy Loading**: Upload images only when chat is initiated
3. **Batch Upload**: Upload multiple images concurrently
4. **CDN Integration**: Cache frequently accessed images

This design provides a robust, user-isolated, multimodal chat system that leverages Gemini's image understanding capabilities while maintaining privacy and performance.