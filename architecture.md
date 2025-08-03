# 📐 Architecture - AI Slop Detection Browser Extension

## 🔍 System Overview
**FactCheck Eye** is a comprehensive AI slop detection system consisting of a Chrome browser extension and a NestJS backend. The system automatically analyzes Facebook posts in real-time as users scroll, providing instant feedback about whether content appears to be AI-generated "slop" content.

## 🏗️ System Architecture

### High-Level Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Facebook      │    │  Chrome Browser  │    │   NestJS        │
│   Website       │◄──►│   Extension      │◄──►│   Backend       │
│                 │    │                  │    │                 │
│ • User scrolls  │    │ • DOM monitoring │    │ • AI analysis   │
│ • Posts load    │    │ • Content extract│    │ • ML models     │
│ • User interact │    │ • Icon injection │    │ • Response gen  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

---

## 🧱 Component Architecture

### 1. **Browser Extension (Chrome)**

#### **Manifest Configuration**
- **Version:** Manifest V3
- **Permissions:** 
  - `activeTab`, `scripting`, `storage`, `tabs`, `webRequest`
  - Host permissions for `*://*.facebook.com/*`
- **Architecture:** Service Worker + Content Scripts

#### **Content Script (`src/content/index.ts`)**
**Primary Responsibilities:**
- **DOM Monitoring:** Uses MutationObserver to detect new Facebook posts
- **Post Detection:** Advanced algorithm to identify valid Facebook posts (articles & group posts)
- **Content Extraction:** 
  - Automatically expands "See more" collapsed content
  - Extracts text using multiple fallback strategies
  - Handles both feed posts and group posts
- **Icon Injection:** Strategically places fact-check icons in post headers
- **User Interaction:** Handles click events and manages UI states

**Key Features:**
- Debounced scroll handling for performance
- Duplicate post prevention using content-based hashing
- Support for both regular feed and Facebook group posts
- Automatic content expansion for collapsed posts
- Professional icon styling with high z-index visibility

#### **Background Service Worker (`src/background/index.ts`)**
**Primary Responsibilities:**
- **API Communication:** Manages requests to the NestJS backend
- **Message Handling:** Processes fact-check requests from content scripts
- **Error Management:** Handles API failures gracefully
- **Response Processing:** Formats backend responses for display

**Current Implementation:**
- Stubbed API endpoint for development
- Returns mock responses during testing phase
- Extensible for future API integration

#### **Popup Interface (`src/popup/`)**
- User settings and configuration
- Extension status and statistics
- Manual fact-check controls

### 2. **Backend API (NestJS)**

#### **Current State**
- **Framework:** NestJS (Node.js)
- **Status:** Basic scaffolding implemented
- **Location:** `/backend/` directory

#### **Planned Architecture**

##### **API Layer**
```typescript
@Controller('api/v1')
export class FactCheckController {
  @Post('/analyze')
  async analyzeContent(@Body() request: AnalyzeRequest): Promise<AnalyzeResponse>
  
  @Get('/health')
  async healthCheck(): Promise<HealthResponse>
}
```

##### **Service Layer**
```typescript
@Injectable()
export class AIAnalysisService {
  // AI model integration
  async detectAISlop(content: string): Promise<AIAnalysisResult>
  
  // Content preprocessing
  async preprocessContent(content: string): Promise<string>
  
  // Confidence scoring
  async calculateConfidence(features: ContentFeatures): Promise<number>
}
```

##### **AI Detection Pipeline**
1. **Content Preprocessing**
   - Text normalization and cleaning
   - Language detection
   - Spam/duplicate filtering

2. **Feature Extraction**
   - Writing style analysis
   - Pattern recognition
   - Sentiment analysis
   - Repetitive phrase detection

3. **AI Model Integration**
   - Integration with AI detection models (e.g., GPTZero, AI classifier)
   - Multiple model ensemble for improved accuracy
   - Confidence scoring algorithms

4. **Response Generation**
   - Verdict classification (AI slop / Human content / Uncertain)
   - Confidence percentage
   - Human-readable explanations

---

## 🔄 Data Flow Architecture

### **Real-time Analysis Flow**
```
1. User scrolls Facebook feed
   ↓
2. Extension detects new posts via MutationObserver
   ↓
3. Post content extracted (including "See more" expansion)
   ↓
4. Automatic analysis triggered (no user click required)
   ↓
5. Content sent to NestJS backend via Background Service Worker
   ↓
6. Backend processes content through AI detection pipeline
   ↓
7. Response returned with verdict, confidence, explanation
   ↓
8. Extension displays result via icon color/tooltip
   ↓
9. User can click for detailed explanation overlay
```

### **API Communication**
```typescript
// Request Format
interface AnalyzeRequest {
  content: string;
  postId: string;
  metadata?: {
    author?: string;
    timestamp?: string;
    postType: 'feed' | 'group';
  };
}

// Response Format
interface AnalyzeResponse {
  verdict: 'ai_slop' | 'human_content' | 'uncertain';
  confidence: number; // 0-1
  explanation: string;
  features?: {
    repetitivePatterns: boolean;
    aiLanguageMarkers: string[];
    stylisticInconsistencies: boolean;
  };
  processingTime: number;
}
```

---

## 🎯 Key Features & Capabilities

### **Browser Extension Features**
- ✅ **Automatic Post Detection:** Works on both feed and group posts
- ✅ **Smart Content Extraction:** Handles collapsed content automatically  
- ✅ **Professional UI Integration:** Non-intrusive icon placement
- ✅ **Performance Optimized:** Debounced scroll handling, duplicate prevention
- ✅ **Robust Post Identification:** Multiple fallback strategies for post detection
- ✅ **Real-time Processing:** Immediate analysis as posts load

### **Backend AI Analysis** (Planned)
- 🔄 **Multi-Model Ensemble:** Combine multiple AI detection approaches
- 🔄 **Feature-Rich Analysis:** Writing style, pattern recognition, sentiment
- 🔄 **Confidence Scoring:** Probability-based verdicts with explanations
- 🔄 **Performance Monitoring:** Response time tracking and optimization
- 🔄 **Scalable Architecture:** Handle high-volume requests efficiently

---

## 🔧 Technical Implementation Details

### **Extension Performance Optimizations**
- **Debounced Scroll Handling:** 250ms delay to prevent excessive processing
- **Content-Based Post Hashing:** Prevents duplicate analysis using Base64 encoded content fingerprints
- **Strategic DOM Targeting:** Multiple fallback strategies for icon placement
- **Memory Management:** Proper cleanup of observers and event listeners

### **Content Extraction Strategy**
1. **Primary:** `[data-ad-comet-preview="message"]` selector
2. **Secondary:** Alternative data attribute selectors
3. **Fallback:** DOM tree traversal with content filtering
4. **Enhancement:** Automatic "See more" button clicking for expanded content

### **Post Detection Algorithm**
```typescript
// Multi-criteria post validation
const isValidPost = (element: HTMLElement) => {
  const isArticle = element.tagName === 'article';
  const hasAuthor = element.querySelector('h2, h3, h4') !== null;
  const hasInteractions = hasLikeCommentShare(element);
  const hasContent = element.textContent.length > 20;
  
  return (isArticle || hasAuthor) && hasInteractions && hasContent;
};
```

---

## 🔐 Security & Privacy

### **Data Protection**
- **No Data Storage:** Content not stored locally or transmitted to third parties
- **Minimal Data Collection:** Only analyzed content sent to backend
- **User Control:** Manual activation via icon clicks (current implementation)
- **Scope Limitation:** Only operates on facebook.com domain

### **Security Measures**
- **Content-Security-Policy:** Strict CSP for extension pages
- **Host Permissions:** Limited to Facebook domains only
- **API Validation:** Input sanitization and validation on backend
- **HTTPS Only:** Secure communication channels

---

## 🚀 Development & Deployment

### **Project Structure**
```
fact-check-extension/
├── browser-extension/          # Chrome extension
│   ├── src/
│   │   ├── content/           # Content scripts
│   │   ├── background/        # Service worker
│   │   ├── popup/            # Extension popup
│   │   └── styles/           # CSS styling
│   └── public/               # Static assets
│
└── backend/                   # NestJS API server
    ├── src/
    │   ├── controllers/       # API endpoints
    │   ├── services/         # Business logic
    │   └── models/           # Data models
    └── test/                 # Test suites
```

### **Technology Stack**
- **Frontend:** TypeScript, Chrome Extension APIs, CSS3
- **Backend:** NestJS, Node.js, TypeScript
- **Build Tools:** Webpack, ESLint, Prettier
- **AI Integration:** TBD (GPTZero, OpenAI, custom models)

---

## 🔮 Future Enhancements

### **Phase 1: Core AI Integration**
- Implement AI detection models in backend
- Add confidence scoring algorithms
- Create explanation generation system

### **Phase 2: Advanced Features**
- Multi-language support
- Custom AI model training
- User feedback integration
- Performance analytics dashboard

### **Phase 3: Platform Expansion**  
- Support for additional social media platforms
- Mobile browser extension
- API rate limiting and caching
- Advanced reporting features
