/**
 * Response type for AI slop detection results from the API
 */
type AiSlopResponse = {
  /** Whether the content is AI-generated slop */
  isAiSlop: boolean;
  /** Confidence score of the analysis (0-1) - legacy */
  confidence: number;
  /** Human-readable explanation of the analysis result */
  reasoning: string;

  // Separate AI probability and confidence for each modality
  /** Text AI probability (0.0 = human, 1.0 = AI) */
  textAiProbability?: number;
  /** Text analysis confidence */
  textConfidence?: number;
  /** Image AI probability (0.0 = human, 1.0 = AI) */
  imageAiProbability?: number;
  /** Image analysis confidence */
  imageConfidence?: number;
  /** Video AI probability (0.0 = human, 1.0 = AI) */
  videoAiProbability?: number;
  /** Video analysis confidence */
  videoConfidence?: number;

  /** Detailed analysis features */
  analysisDetails: Record<string, unknown>;
  /** Processing time in milliseconds */
  processingTime: number;
  /** Analysis timestamp */
  timestamp: string;
};

/**
 * Response type for chat API
 */
type ChatResponse = {
  /** The AI assistant response */
  id: string;
  /** The response message */
  message: string;
  /** Suggested follow-up questions */
  suggested_questions: string[];
  /** Additional context */
  context?: Record<string, unknown>;
  /** Response timestamp */
  timestamp: string;
};

/**
 * Background service for handling AI slop detection and chat operations
 * Manages communication between the content script and backend API
 */
class BackgroundService {
  /** Base URL for the backend API */
  private readonly API_BASE_URL = 'http://localhost:4000/api/v1';
  /** Endpoint for post processing (detection and analysis) */
  private readonly PROCESS_ENDPOINT = `${this.API_BASE_URL}/posts/process`;
  /** Endpoint for chat functionality */
  private readonly CHAT_ENDPOINT = `${this.API_BASE_URL}/chat/send`;

  constructor() {
    this.initialize();
  }

  /**
   * Initializes the background service
   * Sets up message listeners for communication with content scripts
   */
  private initialize(): void {
    this.setupMessageListeners();
    this.setupActionListener();
  }

  /**
   * Sets up Chrome runtime message listeners
   * Handles incoming AI slop detection and chat requests from content scripts
   */
  private setupMessageListeners(): void {
    // Listen for messages from content scripts
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      if (message.type === 'AI_SLOP_REQUEST') {
        this.handleAiSlopRequest(
          message.content,
          message.postId,
          message.imageUrls,
          message.videoUrls
        )
          .then(sendResponse)
          .catch(error => {
            console.error('AI slop detection error:', error);
            sendResponse({
              error: 'Failed to analyze content for AI slop',
              details: error.message,
            });
          });
        return true; // Indicates we'll respond asynchronously
      } else if (message.type === 'CHAT_REQUEST') {
        this.handleChatRequest(message)
          .then(sendResponse)
          .catch(error => {
            console.error('Chat request error:', error);
            sendResponse({
              error: 'Failed to process chat request',
              details: error.message,
            });
          });
        return true; // Indicates we'll respond asynchronously
      }
    });
  }

  /**
   * Sets up Chrome action listener for extension icon clicks
   * Sends message to content script to toggle chat window
   */
  private setupActionListener(): void {
    chrome.action.onClicked.addListener(tab => {
      // Only activate on Facebook pages
      if (tab.url && tab.url.includes('facebook.com') && tab.id) {
        chrome.tabs.sendMessage(tab.id, {
          type: 'TOGGLE_CHAT_WINDOW',
        });
      }
    });
  }

  /**
   * Handles AI slop detection requests by communicating with the backend API
   * @param content - The text content of the Facebook post to analyze
   * @param postId - Unique identifier for the post
   * @param imageUrls - Array of image URLs from the post
   * @param videoUrls - Array of video URLs from the post
   * @returns Promise resolving to AI slop analysis results
   * @throws Error if API request fails
   */
  private async handleAiSlopRequest(
    content: string,
    postId: string,
    imageUrls?: string[],
    videoUrls?: string[]
  ): Promise<AiSlopResponse> {
    console.log(`[Background] 🔍 Analyzing content for post ${postId}:`, {
      contentLength: content.length,
      contentPreview: content.substring(0, 100) + '...',
      imageCount: imageUrls?.length || 0,
      videoCount: videoUrls?.length || 0,
      endpoint: this.PROCESS_ENDPOINT,
    });

    try {
      const requestBody = {
        content,
        post_id: postId, // Backend expects post_id not postId
        author: null, // Default to null for now - could be extracted in future
        image_urls: imageUrls || [],
        video_urls: videoUrls || [],
      };

      console.log('[Background] 📤 Sending request:', requestBody);

      const response = await fetch(this.PROCESS_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      console.log(`[Background] 📥 Response status: ${response.status}`);

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`[Background] ❌ HTTP error ${response.status}:`, errorText);
        throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
      }

      const data = await response.json();
      console.log('[Background] ✅ Analysis successful:', data);

      // Transform backend response to match expected format
      return {
        isAiSlop: data.verdict === 'ai_slop',
        confidence: data.confidence,
        reasoning: data.explanation,
        // Include separate probability and confidence values
        textAiProbability: data.text_ai_probability,
        textConfidence: data.text_confidence,
        imageAiProbability: data.image_ai_probability,
        imageConfidence: data.image_confidence,
        videoAiProbability: data.video_ai_probability,
        videoConfidence: data.video_confidence,
        analysisDetails: {
          verdict: data.verdict,
          postId: data.post_id || postId, // Use response post_id or fallback
        },
        processingTime: 0,
        timestamp: data.timestamp,
      };
    } catch (error) {
      console.error('[Background] ❌ AI slop detection API request failed:', error);

      // More detailed error logging
      if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
        console.error('[Background] 🚫 Network error - possible CORS or connection issue');
        console.error('[Background] 🔍 Check if backend is running on port 4000');
        console.error('[Background] 🔍 Check extension permissions in manifest.json');
      }

      throw error;
    }
  }

  /**
   * Handles chat requests by communicating with the backend chat API
   * @param message - The chat message data
   * @returns Promise resolving to chat response
   * @throws Error if API request fails
   */
  private async handleChatRequest(message: {
    postId: string;
    message: string;
    postContent: string;
    previousAnalysis?: Record<string, unknown>;
    conversationHistory?: unknown[];
  }): Promise<ChatResponse> {
    try {
      const response = await fetch(this.CHAT_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          post_id: message.postId,
          message: message.message,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Chat API request failed:', error);
      throw error;
    }
  }

  /**
   * Validates if a URL is eligible for AI slop detection
   * @param url - The URL to validate
   * @returns boolean indicating if URL is valid for AI slop detection
   */
  private isValidUrl(url: string): boolean {
    return url.includes('facebook.com');
  }
}

// Initialize the background service when the extension loads
new BackgroundService();
