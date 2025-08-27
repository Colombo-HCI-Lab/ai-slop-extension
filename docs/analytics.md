# Analytics & Metrics Collection

Technical documentation for the comprehensive analytics system in the AI Slop Detection browser extension.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Browser        │    │  FastAPI        │    │  PostgreSQL     │
│  Extension      │───▶│  Backend        │───▶│  Database       │
│                 │    │                 │    │                 │
│ ▪ MetricsManager│    │ ▪ AnalyticsAPI  │    │ ▪ 6 Analytics   │
│ ▪ Event Batching│    │ ▪ EventProcessor│    │   Tables        │
│ ▪ Full Collection│    │ ▪ Dashboard API │    │ ▪ Indexed Queries│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Data Dictionary

### Table: `user`
Stores user behavior patterns and system information.

| Column | Type | Description |
|--------|------|-------------|
| `id` | VARCHAR(36) | Primary key, unique user identifier |
| `extension_user_id` | VARCHAR(255) | Unique extension-generated user ID |
| `avg_scroll_speed` | FLOAT | Average scroll speed in pixels/ms |
| `avg_posts_per_minute` | FLOAT | Average posts viewed per minute |
| `total_posts_viewed` | INTEGER | Cumulative posts viewed count |
| `total_interactions` | INTEGER | Cumulative interaction count |
| `browser_info` | JSON | Browser name, version, platform details |
| `timezone` | VARCHAR(50) | User timezone (e.g., America/New_York) |
| `locale` | VARCHAR(10) | User locale (e.g., en-US) |
| `experiment_groups` | JSON | A/B test group assignments |
| `first_seen_at` | TIMESTAMP | First activity timestamp |
| `last_active_at` | TIMESTAMP | Most recent activity timestamp |
| `created_at` | TIMESTAMP | Record creation timestamp |
| `updated_at` | TIMESTAMP | Record last update timestamp |

### Table: `user_post_analytics`
Detailed metrics for each user-post interaction.

| Column | Type | Description |
|--------|------|-------------|
| `id` | VARCHAR(36) | Primary key |
| `user_id` | VARCHAR(36) | Foreign key to user table |
| `post_id` | VARCHAR(255) | Foreign key to post table |
| `interaction_type` | VARCHAR(20) | Type: viewed, clicked, shared, etc. |
| `backend_response_time_ms` | INTEGER | API response time in milliseconds |
| `time_to_interaction_ms` | INTEGER | Time from view to interaction |
| `icon_visibility_duration_ms` | INTEGER | AI icon visibility duration |
| `reading_time_ms` | INTEGER | Estimated reading time |
| `scroll_depth_percentage` | FLOAT | Maximum scroll depth (0-100) |
| `viewport_time_ms` | INTEGER | Time post was in viewport |
| `chat_session_count` | INTEGER | Number of chat sessions initiated |
| `total_chat_duration_ms` | INTEGER | Total chat time for this post |
| `total_messages_sent` | INTEGER | Total messages in chats |
| `suggested_questions_used` | INTEGER | Count of suggested questions clicked |
| `accuracy_feedback` | VARCHAR(20) | User feedback: correct/incorrect/unsure |
| `times_viewed` | INTEGER | Number of times post was viewed |
| `first_viewed_at` | TIMESTAMP | First view timestamp |
| `last_viewed_at` | TIMESTAMP | Most recent view timestamp |
| `interaction_at` | TIMESTAMP | Interaction event timestamp |
| `created_at` | TIMESTAMP | Record creation timestamp |
| `updated_at` | TIMESTAMP | Record last update timestamp |

### Table: `analytics_event`
Low-level event tracking for all user activities.

| Column | Type | Description |
|--------|------|-------------|
| `id` | VARCHAR(36) | Primary key |
| `user_id` | VARCHAR(36) | Foreign key to user table |
| `session_id` | VARCHAR(36) | Foreign key to user_session_enhanced |
| `post_id` | VARCHAR(255) | Foreign key to post table (optional) |
| `event_type` | VARCHAR(100) | Event identifier (e.g., scroll_behavior) |
| `event_category` | VARCHAR(50) | Category: interaction/performance/error |
| `event_value` | FLOAT | Numeric value associated with event |
| `event_label` | VARCHAR(255) | Human-readable event label |
| `event_metadata` | JSON | Additional event-specific data |
| `client_timestamp` | TIMESTAMP | Client-side event timestamp |
| `server_timestamp` | TIMESTAMP | Server-side received timestamp |
| `created_at` | TIMESTAMP | Record creation timestamp |

### Table: `user_session_enhanced`
Comprehensive session behavior tracking.

| Column | Type | Description |
|--------|------|-------------|
| `id` | VARCHAR(36) | Primary key |
| `user_id` | VARCHAR(36) | Foreign key to user table |
| `session_token` | VARCHAR(255) | Unique session identifier |
| `ip_hash` | VARCHAR(64) | Hashed IP for geographic analytics |
| `user_agent` | TEXT | Full user agent string |
| `duration_seconds` | INTEGER | Total session duration |
| `posts_viewed` | INTEGER | Posts viewed in session |
| `posts_analyzed` | INTEGER | Posts analyzed by AI |
| `posts_interacted` | INTEGER | Posts with user interaction |
| `avg_scroll_speed` | FLOAT | Session average scroll speed |
| `avg_posts_per_minute` | FLOAT | Session viewing rate |
| `total_scroll_distance` | INTEGER | Total pixels scrolled |
| `active_time_seconds` | INTEGER | Active browsing time |
| `idle_time_seconds` | INTEGER | Idle/inactive time |
| `started_at` | TIMESTAMP | Session start timestamp |
| `ended_at` | TIMESTAMP | Session end timestamp |
| `end_reason` | VARCHAR(50) | Reason: user_logout/timeout/browser_close |
| `created_at` | TIMESTAMP | Record creation timestamp |
| `updated_at` | TIMESTAMP | Record last update timestamp |

### Table: `chat_session`
Chat interaction analytics and metrics.

| Column | Type | Description |
|--------|------|-------------|
| `id` | VARCHAR(36) | Primary key |
| `user_post_analytics_id` | VARCHAR(36) | Foreign key to user_post_analytics |
| `session_token` | VARCHAR(255) | Unique chat session identifier |
| `duration_ms` | INTEGER | Total chat duration in milliseconds |
| `message_count` | INTEGER | Total messages exchanged |
| `user_message_count` | INTEGER | Messages sent by user |
| `assistant_message_count` | INTEGER | Messages sent by assistant |
| `suggested_question_clicks` | INTEGER | Suggested questions used |
| `average_response_time_ms` | INTEGER | Average assistant response time |
| `max_response_time_ms` | INTEGER | Maximum response time |
| `ended_by` | VARCHAR(20) | How session ended: close/timeout/satisfied |
| `satisfaction_rating` | INTEGER | User rating 1-5 |
| `started_at` | TIMESTAMP | Chat start timestamp |
| `ended_at` | TIMESTAMP | Chat end timestamp |
| `created_at` | TIMESTAMP | Record creation timestamp |
| `updated_at` | TIMESTAMP | Record last update timestamp |

### Table: `performance_metric`
System performance and health metrics.

| Column | Type | Description |
|--------|------|-------------|
| `id` | VARCHAR(36) | Primary key |
| `metric_name` | VARCHAR(100) | Metric identifier |
| `metric_value` | FLOAT | Numeric metric value |
| `metric_unit` | VARCHAR(50) | Unit of measurement (ms, bytes, etc.) |
| `endpoint` | VARCHAR(255) | API endpoint associated with metric |
| `timestamp` | TIMESTAMP | Metric collection timestamp |
| `metric_metadata` | JSON | Additional metric context |
| `created_at` | TIMESTAMP | Record creation timestamp |

## Event Types Collected

### User Behavior Events
- `scroll_behavior` - Scroll patterns, speed, direction
- `post_viewport_enter` - Post enters viewport
- `post_viewport_exit` - Post leaves viewport
- `post_view` - Post viewed by user
- `icon_click` - AI detection icon clicked
- `icon_hover` - AI detection icon hovered

### Performance Events
- `performance_timing` - API response times
- `detection_performance` - AI model processing times
- `page_load` - Page loading metrics
- `api_timing` - Backend API performance

### Chat Events
- `chat_start` - Chat session initiated
- `chat_end` - Chat session terminated
- `chat_message` - Message sent in chat
- `satisfaction_rating` - User satisfaction score

### Session Events
- `session_start` - User session begins
- `session_end` - User session ends
- `page_hidden` - Tab becomes inactive
- `page_visible` - Tab becomes active

## Event Schema

```typescript
interface AnalyticsEvent {
  type: string;                      // Event identifier
  category: string;                  // 'interaction' | 'performance' | 'error'
  value?: number;                    // Numeric value
  label?: string;                    // Event label
  metadata?: Record<string, unknown>; // Additional data
  clientTimestamp: string;           // ISO 8601 timestamp
}
```

## API Endpoints

### POST `/api/v1/analytics/init-user`
Initialize user analytics profile.

**Request:**
```json
{
  "extension_user_id": "ext_user_12345",
  "browser_info": {
    "name": "Chrome",
    "version": "120.0.0",
    "platform": "linux"
  },
  "timezone": "America/New_York",
  "locale": "en-US"
}
```

**Response:**
```json
{
  "user_id": "usr_abc123def456",
  "session_id": "sess_789xyz",
  "experiment_groups": ["variant_a", "feature_beta"]
}
```

### POST `/api/v1/analytics/events/batch`
Submit batch of analytics events.

**Request:**
```json
{
  "session_id": "sess_789xyz",
  "events": [
    {
      "type": "post_view",
      "category": "interaction",
      "metadata": {"postId": "fb_123"},
      "clientTimestamp": "2024-12-08T15:30:45.123Z"
    }
  ]
}
```

### GET `/api/v1/analytics/dashboard/{user_id}`
Retrieve analytics dashboard data.

**Response:**
```json
{
  "user_id": "usr_abc123def456",
  "interaction_stats": {
    "total_posts_viewed": 1250,
    "total_interactions": 89,
    "avg_viewing_time_ms": 6500
  },
  "session_stats": {
    "total_sessions": 32,
    "avg_session_duration_s": 420,
    "avg_posts_per_session": 39.1
  },
  "chat_stats": {
    "total_chats": 23,
    "avg_chat_duration_ms": 65000,
    "satisfaction_avg": 4.2
  }
}
```

## Data Formats

### Post Metadata
```json
{
  "postId": "fb_123456789",
  "contentType": "text_with_image",
  "contentLength": 250,
  "hasMedia": true,
  "aiConfidence": 0.87,
  "detectionModel": "clipbased_v2"
}
```

### Performance Metadata
```json
{
  "endpoint": "/api/v1/detect/analyze",
  "durationMs": 450,
  "statusCode": 200,
  "requestSize": 1024,
  "responseSize": 2048
}
```

### User Agent Metadata
```json
{
  "browser": "Chrome",
  "version": "120.0.6099.71",
  "platform": "Linux x86_64",
  "mobile": false,
  "language": "en-US"
}
```