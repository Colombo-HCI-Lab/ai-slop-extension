/**
 * Raw API response from the backend (snake_case)
 */
type ApiDetectionResponse = {
  verdict: string;
  confidence: number;
  explanation: string;
  text_ai_probability?: number;
  text_confidence?: number;
  image_ai_probability?: number;
  image_confidence?: number;
  video_ai_probability?: number;
  video_confidence?: number;
  post_id?: string;
  timestamp: string;
};

/**
 * Normalized response type for AI slop detection results (camelCase)
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
 * Chat history response from the API
 */
type ChatHistoryResponse = {
  messages: ChatMessage[];
  total_messages?: number;
};

/**
 * Individual chat message from history
 */
type ChatMessage = {
  role: 'user' | 'assistant';
  message: string;
  created_at: string;
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
  private readonly API_BASE_URL = `${process.env.BACKEND_URL}/api/v1`;
  /** Endpoint for post processing (detection and analysis) */
  private readonly PROCESS_ENDPOINT = `${this.API_BASE_URL}/posts/process`;
  /** Endpoint for chat functionality */
  private readonly CHAT_ENDPOINT = `${this.API_BASE_URL}/chat/send`;

  /** In-flight AI requests to de-duplicate by content key */
  private inFlightAiRequests: Map<string, Promise<AiSlopResponse>> = new Map();

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
          message.videoUrls,
          message.postUrl,
          message.hasVideos
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
      } else if (message.type === 'CHAT_HISTORY_REQUEST') {
        this.handleChatHistoryRequest(message.postId, message.userId)
          .then(sendResponse)
          .catch(error => {
            console.error('Chat history request error:', error);
            sendResponse({ error: 'Failed to load chat history', details: error.message });
          });
        return true;
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
   * Normalize raw API response to the expected format
   */
  private normalizeApiResponse(data: ApiDetectionResponse, postId: string): AiSlopResponse {
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
    videoUrls?: string[],
    postUrl?: string,
    hasVideos?: boolean
  ): Promise<AiSlopResponse> {
    console.log(`[Background] 🔍 Analyzing content for post ${postId}:`, {
      contentLength: content.length,
      contentPreview: content.substring(0, 100) + '...',
      imageCount: imageUrls?.length || 0,
      hasVideos: hasVideos || false,
      postUrl: postUrl?.substring(0, 100),
      endpoint: this.PROCESS_ENDPOINT,
    });

    try {
      const requestBody = {
        content,
        post_id: postId, // Backend expects post_id not postId
        author: null, // Default to null for now - could be extracted in future
        image_urls: imageUrls || [],
        video_urls: videoUrls || [], // Keep empty, videos handled by post_url
        post_url: postUrl,
        has_videos: hasVideos || false,
      };

      const key = this.makePostKey(content, postId, imageUrls, videoUrls, postUrl, hasVideos);
      if (this.inFlightAiRequests.has(key)) {
        return this.inFlightAiRequests.get(key)!;
      }

      const reqPromise = this.fetchJsonWithRetry(this.PROCESS_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      })
        .then((data: unknown) => {
          console.log('[Background] ✅ Analysis successful:', data);
          return this.normalizeApiResponse(data as ApiDetectionResponse, postId);
        })
        .finally(() => {
          this.inFlightAiRequests.delete(key);
        });

      this.inFlightAiRequests.set(key, reqPromise);

      const data = await reqPromise;
      console.log('[Background] ✅ Analysis successful:', data);
      return data;
    } catch (error) {
      console.error('[Background] ❌ AI slop detection API request failed:', error);

      // More detailed error logging
      if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
        console.error('[Background] 🚫 Network error - possible CORS or connection issue');
        console.error('[Background] 🔍 Check if backend is running at:', process.env.BACKEND_URL);
        console.error('[Background] 🔍 Check extension permissions in manifest.json');
      }

      throw error;
    }
  }

  /** Fetch JSON with timeout and limited retries */
  private async fetchJsonWithRetry(
    url: string,
    init: RequestInit,
    opts: { timeoutMs?: number; retries?: number; backoffBaseMs?: number } = {}
  ): Promise<unknown> {
    const timeoutMs = opts.timeoutMs ?? 15000;
    const retries = opts.retries ?? 2;
    const backoffBaseMs = opts.backoffBaseMs ?? 300;

    for (let attempt = 0; ; attempt++) {
      const controller = new AbortController();
      const id = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const res = await fetch(url, { ...init, signal: controller.signal });
        clearTimeout(id);
        if (!res.ok) {
          // Retry on 5xx; no retry on 4xx
          const text = await res.text().catch(() => '');
          if (res.status >= 500 && attempt < retries) {
            const delay = backoffBaseMs * Math.pow(2, attempt);
            await new Promise(r => setTimeout(r, delay));
            continue;
          }
          throw new Error(`HTTP ${res.status}: ${text}`);
        }
        const data = await res.json();
        return data;
      } catch (err: unknown) {
        clearTimeout(id);
        const error = err as Error;
        if (
          (error.name === 'AbortError' || error.message?.includes('Failed to fetch')) &&
          attempt < retries
        ) {
          const delay = backoffBaseMs * Math.pow(2, attempt);
          await new Promise(r => setTimeout(r, delay));
          continue;
        }
        throw err;
      }
    }
  }

  /** Build a stable key to de-duplicate similar processing requests */
  private makePostKey(
    content: string,
    postId: string,
    imageUrls?: string[],
    videoUrls?: string[],
    postUrl?: string,
    hasVideos?: boolean
  ): string {
    const fingerprint = JSON.stringify({
      cl: content.length,
      c0: content.slice(0, 200),
      ic: imageUrls?.length || 0,
      vc: videoUrls?.length || 0,
      pu: (postUrl || '').slice(0, 200),
      hv: !!hasVideos,
    });
    return `${postId}|${this.hashString(fingerprint)}`;
  }

  private hashString(input: string): string {
    // Simple djb2 hash to short hex string
    let hash = 5381;
    for (let i = 0; i < input.length; i++) {
      hash = (hash * 33) ^ input.charCodeAt(i);
    }
    return (hash >>> 0).toString(16);
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
    userId: string;
    postContent: string;
    previousAnalysis?: Record<string, unknown>;
  }): Promise<ChatResponse> {
    try {
      const data = await this.fetchJsonWithRetry(this.CHAT_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          post_id: message.postId,
          message: message.message,
          user_id: message.userId,
        }),
      });
      return data as ChatResponse;
    } catch (error) {
      console.error('Chat API request failed:', error);
      throw error;
    }
  }

  /** Load chat history via background with timeout/retry */
  private async handleChatHistoryRequest(
    postId: string,
    userId: string
  ): Promise<ChatHistoryResponse> {
    const url = `${this.API_BASE_URL}/chat/history/${encodeURIComponent(postId)}?user_id=${encodeURIComponent(userId)}`;
    const data = await this.fetchJsonWithRetry(url, { method: 'GET' });
    return data as ChatHistoryResponse;
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
