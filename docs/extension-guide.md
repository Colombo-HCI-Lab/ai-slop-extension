# Browser Extension Development Guide

## Overview

The Chrome browser extension provides real-time AI content detection on Facebook, featuring intelligent chat, user analytics, and seamless integration with the FastAPI backend.

## Features

### Core Functionality
- **Real-time Detection**: Instant AI analysis as users browse Facebook
- **Visual Indicators**: Icons and overlays showing detection results
- **Intelligent Chat**: Context-aware conversations about detected content
- **Post Tracking**: Consistent Facebook post ID extraction and tracking
- **Analytics Collection**: User behavior and interaction metrics

### Technical Features
- **Content Script Injection**: Seamless Facebook page integration
- **Background Service**: Handles API communication and data processing
- **Popup Interface**: User settings and detection history
- **Local Storage**: Caching and user preferences
- **Real-time Communication**: Chrome extension messaging APIs

## Architecture

### Extension Components
```
browser-extension/
├── src/
│   ├── content/              # Content scripts (Facebook integration)
│   │   ├── index.ts         # Main content script entry
│   │   ├── postDetector.ts  # Post detection and analysis
│   │   └── chatInterface.ts # Chat UI components
│   ├── background/          # Background service worker
│   │   ├── index.ts         # Main background script
│   │   └── apiClient.ts     # Backend API communication
│   ├── popup/               # Extension popup UI
│   │   ├── index.html       # Popup interface
│   │   ├── index.ts         # Popup logic
│   │   └── styles.css       # Popup styling
│   └── utils/               # Shared utilities
├── dist/                    # Built extension files
├── manifest.json           # Extension manifest
└── tests/                   # Test files
```

## Development Setup

### Prerequisites
- Node.js (v14 or higher)
- npm (v6 or higher)
- Google Chrome browser
- Running backend API (see [Backend Guide](backend-guide.md))

### Installation & Development

1. **Install dependencies:**
   ```bash
   cd browser-extension
   npm install
   ```

2. **Start development build:**
   ```bash
   npm start
   ```

3. **Load extension in Chrome:**
   - Open `chrome://extensions/`
   - Enable "Developer mode"
   - Click "Load unpacked" and select the `dist` directory

4. **Test on Facebook:**
   - Navigate to Facebook
   - Extension should automatically inject detection capabilities

### Development Commands

```bash
# Development
npm start                    # Start development build with watch mode
npm run dev                  # Alternative development command
npm run build               # Create production build

# Testing & Quality
npm test                    # Run test suite
npm run test:watch         # Run tests with watch mode
npm run lint               # Run ESLint
npm run lint:fix           # Fix linting issues automatically
npm run format             # Format code with Prettier

# Build & Package
npm run build:prod         # Production build with optimizations
npm run package            # Create distribution package
npm run clean              # Clean build artifacts
```

## Extension Functionality

### Facebook Post Detection

#### Post ID Extraction
The extension extracts Facebook's numeric post IDs from various sources:

```typescript
// Post ID extraction from URL
const extractPostIdFromUrl = (url: string): string | null => {
  const patterns = [
    /\/posts\/(\d+)/,                    // /posts/123456789
    /story_fbid=(\d+)/,                  // story_fbid=123456789
    /permalink\/(\d+)/                   // permalink/123456789
  ];
  
  for (const pattern of patterns) {
    const match = url.match(pattern);
    if (match) return match[1];
  }
  return null;
};
```

#### Content Analysis Flow
1. **Detection**: Scan page for new Facebook posts
2. **Extraction**: Extract post content and metadata
3. **ID Generation**: Get consistent Facebook post ID
4. **API Request**: Send to backend for AI analysis
5. **UI Update**: Display detection results with visual indicators

### Chat Interface

#### Chat Window Management
```typescript
// Chat window creation and management
class ChatInterface {
  private chatWindow: HTMLElement;
  private isOpen: boolean = false;
  
  async openChat(postId: string) {
    this.chatWindow = this.createChatWindow(postId);
    this.loadChatHistory(postId);
    this.setupMessageHandling();
    this.isOpen = true;
  }
  
  async sendMessage(postId: string, message: string) {
    const response = await this.apiClient.sendChatMessage(postId, message);
    this.displayMessage(response);
    this.updateSuggestedQuestions(response.suggestedQuestions);
  }
}
```

### Background Service Integration

#### API Communication
```typescript
// Background service API client
class BackgroundAPIClient {
  private baseUrl = 'http://localhost:4000/api/v1';
  
  async analyzePost(postData: PostData): Promise<DetectionResult> {
    const response = await fetch(`${this.baseUrl}/detect/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(postData)
    });
    return response.json();
  }
  
  async sendChatMessage(postId: string, message: string): Promise<ChatResponse> {
    const response = await fetch(`${this.baseUrl}/chat/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ post_id: postId, message })
    });
    return response.json();
  }
}
```

## User Interface

### Detection Indicators
- **AI Slop Icon**: Red warning icon for AI-generated content
- **Human Content Icon**: Green checkmark for human-written content
- **Uncertain Icon**: Yellow question mark for uncertain detection
- **Loading State**: Animated spinner during analysis

### Chat Interface
- **Floating Chat Window**: Overlay chat interface
- **Message History**: Persistent conversation history
- **Suggested Questions**: Pre-generated follow-up questions
- **Typing Indicators**: Real-time typing feedback

### Settings Panel
- **Detection Sensitivity**: Adjustable confidence thresholds
- **Visual Preferences**: Icon styles and positions
- **Analytics Opt-out**: Privacy controls
- **Backend Configuration**: API endpoint settings

## Analytics & Tracking

### User Interaction Metrics
```typescript
// Analytics event tracking
interface AnalyticsEvent {
  eventType: string;           // 'icon_click', 'chat_open', 'scroll_pause'
  postId: string;             // Facebook post ID
  timestamp: number;          // Event timestamp
  metadata: {                 // Additional event data
    confidence?: number;
    verdict?: string;
    interactionDuration?: number;
  };
}

// Track user interactions
const trackInteraction = async (event: AnalyticsEvent) => {
  await chrome.runtime.sendMessage({
    type: 'ANALYTICS_EVENT',
    event
  });
};
```

### Behavioral Data Collection
- **Scroll Patterns**: Speed and pause duration analysis
- **Interaction Timing**: Time from detection to user action
- **Chat Engagement**: Message frequency and session duration
- **Post Consumption**: Reading time and skip patterns

## Configuration

### Extension Manifest
```json
{
  "manifest_version": 3,
  "name": "AI Slop Detector",
  "version": "1.0.0",
  "permissions": [
    "activeTab",
    "storage",
    "background"
  ],
  "content_scripts": [
    {
      "matches": ["*://*.facebook.com/*"],
      "js": ["content/index.js"],
      "css": ["content/styles.css"]
    }
  ],
  "background": {
    "service_worker": "background/index.js"
  }
}
```

### Environment Configuration
```typescript
// Environment-specific configuration
const config = {
  development: {
    apiBaseUrl: 'http://localhost:4000/api/v1',
    debugMode: true,
    analyticsEnabled: true
  },
  production: {
    apiBaseUrl: 'https://api.ai-slop-detector.com/api/v1',
    debugMode: false,
    analyticsEnabled: true
  }
};
```

## Testing

### Test Structure
```bash
tests/
├── unit/                   # Unit tests for individual components
│   ├── postDetector.test.ts
│   ├── chatInterface.test.ts
│   └── apiClient.test.ts
├── integration/            # Integration tests
│   ├── contentScript.test.ts
│   └── background.test.ts
└── e2e/                   # End-to-end tests
    ├── facebook.test.ts
    └── chat.test.ts
```

### Testing Commands
```bash
# Unit tests
npm test                    # Run all tests
npm run test:unit          # Run unit tests only
npm run test:integration   # Run integration tests
npm run test:e2e          # Run end-to-end tests

# Test coverage
npm run test:coverage      # Generate coverage report
npm run test:watch         # Watch mode for development
```

### Mock Facebook Environment
```typescript
// Test utilities for mocking Facebook DOM
class MockFacebookEnvironment {
  createMockPost(postId: string, content: string): HTMLElement {
    const postElement = document.createElement('div');
    postElement.setAttribute('data-testid', 'post');
    postElement.setAttribute('data-post-id', postId);
    postElement.innerHTML = `<div class="post-content">${content}</div>`;
    return postElement;
  }
  
  simulateUserScroll(): void {
    // Simulate Facebook infinite scroll
    window.dispatchEvent(new Event('scroll'));
  }
}
```

## Building & Deployment

### Development Build
```bash
npm start                   # Development build with watch mode
npm run build:dev          # Single development build
```

### Production Build
```bash
npm run build              # Production build
npm run build:prod         # Production build with optimizations
npm run package            # Create distribution package
```

### Chrome Web Store Submission
1. **Build production version:**
   ```bash
   npm run build:prod
   ```

2. **Test production build:**
   - Load `dist/` directory in Chrome
   - Test all functionality thoroughly
   - Verify permissions and security

3. **Package for submission:**
   ```bash
   npm run package
   ```

4. **Submit to Chrome Web Store:**
   - Upload generated package
   - Complete store listing
   - Submit for review

## Security Considerations

### Content Security Policy
- **Restricted Inline Scripts**: No inline JavaScript execution
- **API Communication**: HTTPS-only in production
- **Data Sanitization**: All user input properly escaped
- **Permission Minimization**: Only required permissions requested

### Privacy Protection
- **No Personal Data**: Only anonymous interaction metrics
- **Local Storage**: Sensitive data stored locally only
- **Opt-out Controls**: User can disable analytics
- **Data Retention**: Automatic cleanup of old data

## Troubleshooting

### Common Issues

#### Extension Not Loading
```bash
# Check for build errors
npm run build

# Verify manifest.json syntax
cat manifest.json | jq .

# Check Chrome extension errors
# Go to chrome://extensions/ and check error console
```

#### API Connection Issues
```bash
# Verify backend is running
curl http://localhost:4000/api/v1/health

# Check CORS configuration
# Ensure backend allows extension origin
```

#### Facebook Integration Problems
```typescript
// Debug content script injection
console.log('Content script loaded:', window.location.href);
console.log('Facebook posts found:', document.querySelectorAll('[data-testid="post"]').length);
```

### Debug Mode
Enable debug mode for detailed logging:
```typescript
// In development builds
if (process.env.NODE_ENV === 'development') {
  console.log('Debug mode enabled');
  window.aiSlopDebug = true;
}
```

## Performance Optimization

### Content Script Optimization
- **Debounced DOM Scanning**: Avoid excessive post detection
- **Efficient Selectors**: Use specific CSS selectors
- **Memory Management**: Clean up event listeners
- **Async Operations**: Non-blocking API calls

### Background Service Optimization
- **Request Batching**: Group multiple API calls
- **Caching Strategy**: Store results locally
- **Connection Pooling**: Reuse HTTP connections
- **Error Handling**: Graceful degradation on API failures