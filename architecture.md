# 📐 architecture.md

## 🔍 Extension Name
**FactCheck Eye** – A Real-Time Misinformation Detection Tool for Facebook

## 🧩 Overview

**FactCheck Eye** is a Google Chrome extension designed to combat the spread of misinformation on Facebook. It integrates directly into the user’s feed and enables real-time fact-checking of posts. By introducing a subtle "eye" icon on each post, users can manually verify the credibility of content with a single click. The extension communicates with a backend API that returns a credibility assessment, which is then displayed as an overlay on the post.

## 🎯 Key Functions

- **UI Integration:** Add an interactive icon to each Facebook post as the user scrolls.
- **User Interaction:** On clicking the icon, extract the post's content (text, possibly media).
- **Fact-Checking:** Send the content to a backend server for misinformation analysis.
- **Response Handling:** Display the result (e.g., “Likely Misinformation”, “Verified”, etc.) as a visual overlay on the corresponding post.

---

## 🛠️ Architecture

### 1. **Manifest & Permissions**
- **manifest.json**
  - `permissions`: `activeTab`, `scripting`, `storage`, `tabs`, `webRequest`
  - `host_permissions`: `*://*.facebook.com/*`, your backend domain
  - `content_scripts`: Runs on Facebook pages (`https://www.facebook.com/*`)
  - `background`: Optional if using messaging

### 2. **Components**

#### a. **Content Script (`content.js`)**
Injected into Facebook pages to:
- Continuously monitor the DOM as the user scrolls
- Detect and identify Facebook posts
- Inject a small clickable “eye” icon into each post
- Capture the content (e.g., post text)
- Display the backend’s response as an overlay on the post

#### b. **Background Script (`background.js`)**
(Optional depending on architecture)
- Handles API requests if needed for CORS isolation or centralized logging

#### c. **Popup / Options Page (Optional)**
- Allow users to configure backend URL, toggle features, etc.

#### d. **Overlay UI**
- Created dynamically in the DOM
- Displays status (e.g., “Analyzing...”) and final result (“True”, “False”, “Uncertain”)

### 3. **Backend API**
The extension communicates with a RESTful backend service:
- **Endpoint:** `POST /factcheck`
- **Request Payload:**
```json
{
  "content": "Text content of the Facebook post"
}
```
- **Response Format:**
```json
{
  "verdict": "misinformation | verified | unknown",
  "confidence": 0.89,
  "explanation": "This post contains claims previously debunked by XYZ source."
}
```

---

## 🔄 Data Flow

1. **DOM Monitor:** Content script listens for changes in Facebook feed.
2. **Icon Injection:** Adds an “eye” button to each new post.
3. **User Clicks Icon:** Extracts post text and sends to backend.
4. **API Response Received:** Verdict and explanation are parsed.
5. **Overlay Rendered:** Post gets a visual overlay displaying fact-check result.

---

## 🔐 Privacy Considerations
- Only user-initiated posts are analyzed.
- No data is stored locally or sent to third parties besides your backend.
- Extension operates only on facebook.com.
