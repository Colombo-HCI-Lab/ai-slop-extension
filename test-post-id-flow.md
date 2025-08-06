# Facebook Post ID Flow Test

This document demonstrates how Facebook post IDs are now used throughout the system.

## Data Flow

### 1. Browser Extension (Content Script)
```javascript
// browser-extension/src/content/index.ts:generatePostId()
const postId = await this.generatePostId(postElement);
// Returns: "24312088291761638" (Facebook's numeric post ID)

// Content script sends to background
chrome.runtime.sendMessage({
  type: 'AI_SLOP_REQUEST',
  content: postContent,
  postId: postId  // "24312088291761638"
});
```

### 2. Browser Extension (Background Service)
```javascript
// browser-extension/src/background/index.ts:handleAiSlopRequest()
const requestBody = {
  content,
  postId,  // "24312088291761638"
};

// Sends to backend API
fetch('http://localhost:4000/api/v1/detect/analyze', {
  method: 'POST',
  body: JSON.stringify(requestBody)
});
```

### 3. Backend API (Detect Controller)
```typescript
// backend/src/detect/detect.controller.ts:detect()
async detect(@Body() detectDto: DetectDto) {
  // detectDto.postId = "24312088291761638"
  const result = await this.detectService.detect(detectDto, context);
  return result;
}
```

### 4. Backend Service (Cache & Database)
```typescript
// backend/src/detect/cache.service.ts:cacheResult()
await this.databaseService.post.upsert({
  where: { postId }, // "24312088291761638"
  create: {
    postId,        // "24312088291761638" (Facebook post ID)
    content,
    verdict,
    confidence,
    explanation
  }
});
```

### 5. Database Schema
```sql
-- Table: post
CREATE TABLE "post" (
    "id" TEXT PRIMARY KEY,           -- cuid() internal ID
    "postId" TEXT UNIQUE NOT NULL,  -- "24312088291761638" (Facebook post ID)
    "content" TEXT NOT NULL,
    "verdict" TEXT NOT NULL,
    "confidence" DOUBLE PRECISION NOT NULL,
    -- ...
);

-- Table: chat (foreign key relationship)
CREATE TABLE "chat" (
    "id" TEXT PRIMARY KEY,
    "postDbId" TEXT NOT NULL,       -- References post.id (internal)
    "role" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    -- ...
    FOREIGN KEY ("postDbId") REFERENCES "post"("id")
);
```

### 6. Chat API Flow
```typescript
// When user chats about a post
async sendMessage(facebookPostId: string, message: string) {
  // 1. Find post by Facebook post ID
  const post = await this.databaseService.post.findUnique({
    where: { postId: facebookPostId }  // "24312088291761638"
  });
  
  // 2. Save chat using internal database ID
  await this.databaseService.chat.create({
    data: {
      postDbId: post.id,  // Internal cuid
      role: 'user',
      message
    }
  });
}
```

## Key Benefits

1. **Consistent Post Identity**: Same Facebook post will always have ID "24312088291761638"
2. **No Duplicate Analysis**: Posts analyzed once are cached by Facebook post ID
3. **Proper Database Relations**: Chat messages correctly linked to posts via foreign keys
4. **Cross-User Consistency**: Multiple users viewing same post see same analysis

## Example URLs → Post IDs

| Facebook URL | Extracted Post ID |
|--------------|------------------|
| `https://www.facebook.com/groups/1638417209555402/posts/24312088291761638/` | `24312088291761638` |
| `https://www.facebook.com/groups/1638417209555402/posts/24335126272791173/` | `24335126272791173` |
| `https://www.facebook.com/groups/1638417209555402/posts/2489476187782829/`  | `2489476187782829`  |

All comment URLs for the same post will extract the same post ID:
- `...posts/24312088291761638/?comment_id=123456` → `24312088291761638`
- `...posts/24312088291761638/?comment_id=789012` → `24312088291761638`