# Analytics & Metrics Collection

This document describes the comprehensive analytics and metrics collection system implemented in the AI Slop Detection browser extension. 

**⚠️ RESEARCH MODE**: This extension is configured for research purposes with full data collection from all users. Users provide consent before receiving the extension.

## Overview

The analytics system tracks user behavior, system performance, and feature usage to support research into AI content detection effectiveness and user interaction patterns. **All metrics are collected by default** from research participants.

## Architecture

### Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Browser        │    │  FastAPI        │    │  PostgreSQL     │
│  Extension      │───▶│  Backend        │───▶│  Database       │
│                 │    │                 │    │                 │
│ ▪ MetricsManager│    │ ▪ AnalyticsAPI  │    │ ▪ 6 Analytics   │
│ ▪ PrivacyManager│    │ ▪ EventProcessor│    │   Tables        │
│ ▪ Event Batching│    │ ▪ Dashboard API │    │ ▪ Indexed Queries│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Key Features

- **Privacy-First Design**: User consent required, data minimization, GDPR compliance
- **Event Batching**: Efficient network usage with configurable batch sizes
- **Real-time Processing**: Immediate analytics event processing
- **Performance Monitoring**: System health and response time tracking
- **Retention Policies**: Automatic data cleanup and archival

## Database Schema

### Core Tables

#### 1. `user` - User Profiles
Stores user behavior patterns and demographics.

```sql
CREATE TABLE user (
    id VARCHAR(36) PRIMARY KEY,
    extension_user_id VARCHAR(255) UNIQUE NOT NULL,
    avg_scroll_speed FLOAT,
    avg_posts_per_minute FLOAT,
    total_posts_viewed INTEGER DEFAULT 0,
    total_interactions INTEGER DEFAULT 0,
    browser_info JSON,
    timezone VARCHAR(50),
    locale VARCHAR(10),
    experiment_groups JSON,
    first_seen_at TIMESTAMP WITH TIME ZONE,
    last_active_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 2. `user_post_analytics` - Post Interaction Tracking
Detailed metrics for each user-post interaction.

```sql
CREATE TABLE user_post_analytics (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES user(id) ON DELETE CASCADE,
    post_id VARCHAR(255) REFERENCES post(post_id) ON DELETE CASCADE,
    interaction_type VARCHAR(20) DEFAULT 'viewed',
    backend_response_time_ms INTEGER,
    time_to_interaction_ms INTEGER,
    icon_visibility_duration_ms INTEGER,
    reading_time_ms INTEGER,
    scroll_depth_percentage FLOAT,
    viewport_time_ms INTEGER,
    chat_session_count INTEGER DEFAULT 0,
    total_chat_duration_ms INTEGER DEFAULT 0,
    total_messages_sent INTEGER DEFAULT 0,
    suggested_questions_used INTEGER DEFAULT 0,
    accuracy_feedback VARCHAR(20),
    times_viewed INTEGER DEFAULT 1,
    first_viewed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_viewed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    interaction_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, post_id)
);
```

#### 3. `analytics_event` - Granular Event Tracking
Low-level event tracking for detailed analytics.

```sql
CREATE TABLE analytics_event (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES user(id) ON DELETE CASCADE,
    session_id VARCHAR(36) REFERENCES user_session_enhanced(id) ON DELETE CASCADE,
    post_id VARCHAR(255) REFERENCES post(post_id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50),
    event_value FLOAT,
    event_label VARCHAR(255),
    event_metadata JSON,
    client_timestamp TIMESTAMP WITH TIME ZONE,
    server_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 4. `user_session_enhanced` - Session Tracking
Comprehensive session behavior tracking.

#### 5. `chat_session` - Chat Analytics
Detailed chat interaction metrics.

#### 6. `performance_metric` - System Performance
Backend performance and health monitoring.

## Data Collection Categories

### 1. User Behavior Analytics

**What is collected:**
- Scroll speed and patterns
- Post viewing time and depth
- Click-through rates on detected AI content
- Feature usage patterns

**Example event:**
```json
{
  "type": "scroll_behavior",
  "category": "interaction", 
  "value": 1.2,
  "metadata": {
    "totalDistance": 1500,
    "direction": "down",
    "speedSamples": 10
  },
  "clientTimestamp": "2024-12-08T15:30:45.123Z"
}
```

### 2. Post Interaction Metrics

**What is collected:**
- Time spent viewing posts
- AI detection icon interactions
- Chat session engagement
- Accuracy feedback

**Example event:**
```json
{
  "type": "post_view",
  "category": "interaction",
  "metadata": {
    "postId": "fb_123456789",
    "elementBounds": {
      "width": 500,
      "height": 300
    },
    "viewportTime": 5200
  },
  "clientTimestamp": "2024-12-08T15:30:45.123Z"
}
```

### 3. Performance Metrics

**What is collected:**
- API response times
- Detection processing duration
- Memory usage patterns
- Error rates and types

**Example event:**
```json
{
  "type": "detection_performance",
  "category": "performance",
  "value": 850,
  "metadata": {
    "postId": "fb_123456789", 
    "verdict": "ai_generated",
    "processingTimeMs": 850,
    "modelUsed": "clipbased_detection"
  },
  "clientTimestamp": "2024-12-08T15:30:45.123Z"
}
```

### 4. Chat Analytics

**What is collected:**
- Conversation length and depth
- Question types and patterns
- User satisfaction ratings
- Feature usage (suggested questions)

**Example data:**
```json
{
  "sessionId": "chat_sess_abc123",
  "durationMs": 120000,
  "messageCount": 12,
  "userMessageCount": 6,
  "assistantMessageCount": 6,
  "suggestedQuestionClicks": 2,
  "satisfactionRating": 4,
  "endedBy": "user_close"
}
```

## Privacy Controls

### Privacy Modes

#### 1. Strict Mode
- Only essential error and security events
- No behavioral tracking
- Minimal metadata collection

#### 2. Balanced Mode (Default)
- Essential events + basic interaction tracking
- Post viewing and icon clicks
- Aggregated performance metrics
- No detailed scroll behavior

#### 3. Full Mode
- All event categories enabled
- Detailed behavioral analytics
- Performance profiling
- A/B testing participation

### GDPR Compliance

#### Consent Management
```typescript
interface ConsentStatus {
  hasConsent: boolean;
  consentDate?: Date;
  consentVersion?: string;
  gdprApplies: boolean;
}
```

#### User Rights
- **Right to Access**: Export all collected data via `/api/v1/analytics/export`
- **Right to Rectification**: Update privacy settings via browser extension
- **Right to Erasure**: Delete all data via `/api/v1/analytics/delete-user`
- **Right to Portability**: JSON export of all user data

#### Data Retention
- **Session Data**: 30 days
- **Interaction Analytics**: 12 months  
- **Performance Metrics**: 6 months
- **Error Logs**: 90 days

## API Endpoints

### Analytics Collection

#### POST `/api/v1/analytics/init-user`
Initialize or retrieve user analytics profile.

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

#### POST `/api/v1/analytics/events/batch`
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

#### POST `/api/v1/analytics/interaction`
Track specific post interaction.

**Request:**
```json
{
  "user_id": "usr_abc123def456",
  "interaction_type": "icon_click",
  "backend_response_time_ms": 245,
  "reading_time_ms": 8500,
  "scroll_depth_percentage": 85.2
}
```

### Analytics Retrieval

#### GET `/api/v1/analytics/dashboard/{user_id}`
Get user analytics dashboard data.

**Query Parameters:**
- `period`: Time period (`7d`, `30d`, `90d`)
- `include_detailed`: Include detailed breakdowns

**Response:**
```json
{
  "user_id": "usr_abc123def456",
  "period": {"start": "2024-11-08", "end": "2024-12-08"},
  "interaction_stats": {
    "total_posts_viewed": 1250,
    "total_interactions": 89,
    "avg_viewing_time_ms": 6500,
    "accuracy_feedback": {
      "correct": 45,
      "incorrect": 8, 
      "unsure": 12
    }
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

#### GET `/api/v1/analytics/export/{user_id}`
Export all user data (GDPR compliance).

**Response:**
```json
{
  "user_data": {
    "user_id": "usr_abc123def456",
    "stats": {...},
    "settings": {...}
  },
  "events": [...],
  "interactions": [...],
  "chat_sessions": [...],
  "exported_at": "2024-12-08T15:30:45.123Z"
}
```

## Usage Examples

### 1. Tracking Post Detection Performance

```typescript
// Backend - after AI detection
await analyticsService.trackPostInteraction({
  user_id: userId,
  post_id: postId,
  interaction_type: 'ai_detected',
  backend_response_time_ms: processingTime,
  metadata: {
    confidence_score: 0.87,
    model_used: 'clipbased_detection',
    content_type: 'image'
  }
});
```

### 2. Monitoring User Engagement

```typescript
// Browser extension - track icon interaction
metricsManager.trackIconInteraction(postId, 'click');

// Results in database:
// user_post_analytics.interaction_type = 'icon_click'
// user_post_analytics.interaction_at = NOW()
// analytics_event with detailed timing data
```

### 3. A/B Testing Integration

```typescript
// Assign user to experiment group
const user = await analyticsService.initializeUser({
  extension_user_id: 'ext_user_12345',
  // ... other data
});

// user.experiment_groups = ['icon_style_v2', 'chat_suggestions_enabled']
// Use experiment_groups to show different UI variants
```

### 4. Performance Monitoring

```typescript
// Track API performance automatically
performance.mark('api-detect-start');
await detectAIContent(postData);
performance.mark('api-detect-end');
performance.measure('api-detect', 'api-detect-start', 'api-detect-end');

// MetricsCollector automatically captures performance measures
// Results in performance_metric table
```

### 5. Chat Quality Analysis

```typescript
// Track chat session metrics
const chatMetrics = {
  session_id: 'chat_sess_xyz789',
  user_post_analytics_id: 'upa_abc123',
  duration_ms: 180000,
  message_count: 16,
  user_message_count: 8,
  assistant_message_count: 8,
  suggested_question_clicks: 3,
  satisfaction_rating: 5,
  ended_by: 'user_satisfied'
};

await analyticsService.recordChatSession(chatMetrics);
```

## Data Formats

### Event Schema
All events follow this standard schema:

```typescript
interface AnalyticsEvent {
  type: string;                    // Event type identifier
  category: string;                // 'interaction' | 'performance' | 'error'
  value?: number;                  // Numeric value (duration, count, etc.)
  label?: string;                  // Human-readable label
  metadata?: Record<string, any>;  // Additional context data
  clientTimestamp: string;         // ISO 8601 timestamp
}
```

### Metadata Standards

#### Post Metadata
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

#### Performance Metadata
```json
{
  "endpoint": "/api/v1/detect/analyze",
  "durationMs": 450,
  "statusCode": 200,
  "requestSize": 1024,
  "responseSize": 2048
}
```

#### User Agent Metadata
```json
{
  "browser": "Chrome",
  "version": "120.0.6099.71",
  "platform": "Linux x86_64",
  "mobile": false,
  "language": "en-US"
}
```

## Development & Testing

### Local Development
```bash
# Enable debug analytics logging
export DEBUG_ANALYTICS=true

# Start with analytics enabled
npm start
```

### Testing Analytics
```bash
# Run analytics integration tests
npm run test:analytics

# Test privacy controls
npm run test:privacy

# Generate test analytics data
npm run analytics:generate-test-data
```

### Analytics Dashboard
Access the developer analytics dashboard:
- **Local**: `http://localhost:4000/analytics/dashboard`
- **Staging**: `https://staging-api.example.com/analytics/dashboard`

## Security & Privacy

### Data Security
- All API communications over HTTPS
- Database connections encrypted (TLS 1.3)
- Personal identifiers hashed using SHA-256
- Regular security audits and updates

### Privacy Safeguards
- No personally identifiable information stored
- IP addresses hashed for geographic analytics only
- User content never transmitted to analytics
- Automatic data expiration and cleanup

### Compliance
- **GDPR**: Full compliance with consent, access, and deletion rights
- **CCPA**: California Consumer Privacy Act compliance
- **SOC 2**: System and Organization Controls certification
- **Privacy by Design**: Privacy considerations built into system architecture

## Monitoring & Alerts

### System Health
- Real-time analytics processing status
- Database performance monitoring  
- API response time tracking
- Error rate thresholds and alerting

### Data Quality
- Event validation and schema enforcement
- Duplicate detection and prevention
- Data consistency checks
- Missing data alerts

### Privacy Compliance
- Consent status monitoring
- Data retention enforcement
- User deletion request tracking
- GDPR compliance reports

---

*Last Updated: December 2024*
*Version: 1.0*