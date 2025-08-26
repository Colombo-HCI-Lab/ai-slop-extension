import '../styles/content.scss';

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

// User identification utilities
const getUserIdentifier = (): string => {
  let userId = localStorage.getItem('ai-slop-user-id');
  if (!userId) {
    userId = crypto.randomUUID();
    localStorage.setItem('ai-slop-user-id', userId);
  }
  return userId;
};

/**
 * Observes and processes Facebook posts to add AI slop detection functionality
 * - Monitors DOM for new posts
 * - Injects AI slop detection icons into posts
 * - Handles AI detection requests and result display
 */
export class FacebookPostObserver {
  /** MutationObserver instance for monitoring DOM changes */
  private observer: MutationObserver;

  /** Set to track processed posts and prevent duplicate processing */
  private processedPosts: Set<string>;

  /** Selector for extracting post content */
  private readonly POST_CONTENT_SELECTOR = '[data-ad-comet-preview="message"]';

  /** List of allowed Facebook group names where the extension should work */
  private readonly ALLOWED_GROUP_NAMES = [
    'Artificial Intelligence & Deep Learning Memes For Back-propagated Poets',
    'Social Media for People',
  ];

  /**
   * Checks if the current page is in an allowed Facebook group
   * @returns boolean indicating if the extension should be active
   */
  private isInAllowedGroup(): boolean {
    const currentGroupName = this.getCurrentGroupName();

    if (!currentGroupName) {
      // Not in a group, extension should NOT work
      return false;
    }

    const isAllowed = this.ALLOWED_GROUP_NAMES.some(
      allowedName =>
        currentGroupName.toLowerCase().includes(allowedName.toLowerCase()) ||
        allowedName.toLowerCase().includes(currentGroupName.toLowerCase())
    );

    console.log(
      `[AI-Slop] Group filtering - Current group: "${currentGroupName}", Allowed: ${isAllowed}`
    );
    return isAllowed;
  }

  /**
   * Extracts the current Facebook group name from the page
   * @returns string group name or null if not in a group
   */
  private getCurrentGroupName(): string | null {
    // Method 1: Check URL pattern for groups
    const url = window.location.href;
    if (!url.includes('/groups/')) {
      return null; // Not in a group
    }

    // Method 2: Look for group name in page title
    const pageTitle = document.title;
    if (pageTitle && pageTitle.includes('|')) {
      // Facebook group titles often have format "Group Name | Facebook"
      const groupName = pageTitle.split('|')[0].trim();
      if (groupName && groupName !== 'Facebook') {
        return groupName;
      }
    }

    // Method 3: Look for group name in DOM elements
    const selectors = [
      'h1[dir="auto"]', // Main group title
      '[data-pagelet="GroupsRHCHeader"] h1',
      '[role="main"] h1',
      'a[href*="/groups/"] h1', // Group header link
      '[data-testid="group_name"] h1',
    ];

    for (const selector of selectors) {
      const element = document.querySelector(selector);
      if (element && element.textContent && element.textContent.trim().length > 0) {
        const groupName = element.textContent.trim();
        // Filter out generic Facebook elements
        if (groupName && !['Facebook', 'Home', 'Groups'].includes(groupName)) {
          return groupName;
        }
      }
    }

    // Method 4: Look for breadcrumb navigation
    const breadcrumbLinks = document.querySelectorAll('nav a[href*="/groups/"]');
    for (const link of breadcrumbLinks) {
      if (link.textContent && link.textContent.trim().length > 3) {
        const groupName = link.textContent.trim();
        if (!['Groups', 'Facebook'].includes(groupName)) {
          return groupName;
        }
      }
    }

    console.log(`[AI-Slop] Could not determine group name from URL: ${url}`);
    return 'Unknown Group';
  }

  /**
   * Determines if an element is a Facebook post by checking multiple characteristics
   * Works for both regular feed posts and Facebook group posts
   * @param element - The HTML element to check
   * @returns boolean indicating if the element is a Facebook post
   */
  private isFacebookPost(element: HTMLElement): boolean {
    // Handle different post container types:
    // 1. Article elements (regular feed posts)
    // 2. Divs containing group posts with specific structure
    const isArticle = element.tagName.toLowerCase() === 'article';

    // For Facebook groups, posts might be contained in divs with specific structure
    // Look for elements that contain author headings and interaction buttons
    const hasAuthorHeading = element.querySelector('h2, h3, h4') !== null;
    const authorElement = element.querySelector('h2, h3, h4');
    const authorText = authorElement?.textContent?.substring(0, 30) || 'N/A';

    // Check for interaction buttons using text content
    const buttons = element.querySelectorAll('button');
    let hasLike = false;
    let hasComment = false;
    let hasShare = false;

    buttons.forEach(button => {
      const text = button.textContent?.toLowerCase() || '';
      if (text.includes('like')) hasLike = true;
      if (text.includes('comment')) hasComment = true;
      if (text.includes('share')) hasShare = true;
    });

    // Also check for aria-label attributes
    const hasLikeAria =
      element.querySelector('button[aria-label*="Like"], [aria-label*="like"]') !== null;
    const hasCommentAria =
      element.querySelector('button[aria-label*="Comment"], [aria-label*="comment"]') !== null;
    const hasShareAria =
      element.querySelector('button[aria-label*="Share"], [aria-label*="share"]') !== null;

    // Check for post content indicators
    const hasDataAdPreview = element.querySelector('[data-ad-comet-preview="message"]') !== null;
    const hasPostContent = element.textContent && element.textContent.trim().length > 20;

    // Enhanced validation for group posts
    const hasInteractionButtons =
      hasLike || hasComment || hasShare || hasLikeAria || hasCommentAria || hasShareAria;

    // A valid post should have:
    // 1. Either be an article OR have author heading
    // 2. Have interaction buttons
    // 3. Have some meaningful content OR data-ad-comet-preview attribute
    const isValidPost =
      (isArticle || hasAuthorHeading) &&
      hasInteractionButtons &&
      (hasPostContent || hasDataAdPreview);

    // Only log when we find a valid post
    if (isValidPost) {
      console.group('[AI-Slop] ✅ POST DETECTED!');
      console.log('👤 Author:', authorText);
      console.log('📊 Post type:', isArticle ? 'Article' : 'Group Post');
      console.log('🔍 Found buttons:', buttons.length);
      console.log('📊 Interactions found:', {
        like: hasLike || hasLikeAria,
        comment: hasComment || hasCommentAria,
        share: hasShare || hasShareAria,
      });
      console.log('📝 Has data-ad-comet-preview:', hasDataAdPreview);
      console.log('📄 Content length:', element.textContent?.length || 0);
      console.groupEnd();
    }

    return isValidPost;
  }

  /** Debounce timer for scroll handling */
  private scrollDebounceTimer: number | undefined;

  /** Debounce delay in milliseconds */
  private readonly SCROLL_DEBOUNCE_DELAY = 250;

  /** Bound scroll handler for proper event cleanup */
  private readonly boundHandleScroll: () => void;

  /** Video processor for Facebook videos (disabled - using yt-dlp) */
  // private videoProcessor: FacebookVideoProcessor;

  constructor() {
    console.group('[AI-Slop] 🚀 Initializing Facebook Post Observer');
    console.log('📅 Timestamp:', new Date().toISOString());
    console.log('🌐 URL:', window.location.href);
    console.log('🏷️ Page title:', document.title);

    this.processedPosts = new Set();
    this.boundHandleScroll = this.handleScroll.bind(this);
    this.observer = new MutationObserver(this.handleMutations.bind(this));
    // this.videoProcessor = new FacebookVideoProcessor(); // Disabled - using yt-dlp

    console.log('⚙️ Observer setup complete');
    console.groupEnd();

    this.initialize();
  }

  /**
   * Cleans up resources used by the observer
   * Should be called when the observer is no longer needed
   */
  public cleanup(): void {
    this.observer.disconnect();
    this.processedPosts.clear();

    // Clean up video processor (disabled)
    // if (this.videoProcessor) {
    //   this.videoProcessor.cleanup();
    // }

    // Remove scroll event listener
    window.removeEventListener('scroll', this.boundHandleScroll);

    // Clear any existing debounce timer
    if (this.scrollDebounceTimer) {
      window.clearTimeout(this.scrollDebounceTimer);
    }
  }

  /**
   * Initializes the Facebook post observer
   * Sets up mutation observer and processes existing posts
   */
  private initialize(): void {
    // Start observing the DOM for changes with enhanced configuration
    this.observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      characterData: true,
    });

    // Add scroll event listener with debouncing
    window.addEventListener('scroll', this.boundHandleScroll);

    // Process any existing posts with a small delay to allow Facebook to load URLs
    setTimeout(() => {
      console.log('[AI-Slop] Running initial post processing with URL-first strategy...');
      this.processExistingPosts().catch(error => {
        console.error('[AI-Slop] Error processing existing posts:', error);
      });
    }, 500);

    // Add delayed processing to catch posts that load after initialization
    // This fixes the issue where the first post is missed due to timing
    setTimeout(() => {
      console.log('[AI-Slop] Running delayed post processing to catch missed posts...');
      this.processExistingPosts().catch(error => {
        console.error('[AI-Slop] Error in delayed post processing:', error);
      });
    }, 1000);

    // Add additional delayed processing for slower connections
    setTimeout(() => {
      console.log('[AI-Slop] Running secondary delayed post processing...');
      this.processExistingPosts().catch(error => {
        console.error('[AI-Slop] Error in secondary delayed post processing:', error);
      });
    }, 3000);

    // Set up periodic rescanning to catch any posts that are still missed
    setInterval(() => {
      console.debug('[AI-Slop] Periodic post scan to ensure no posts are missed');
      this.processExistingPosts().catch(error => {
        console.error('[AI-Slop] Error in periodic post processing:', error);
      });
    }, 10000); // Every 10 seconds
  }

  /**
   * Handles scroll events with debouncing to process new posts
   * Added to handle Facebook's infinite scrolling behavior
   */
  private handleScroll(): void {
    // Clear existing timer
    if (this.scrollDebounceTimer) {
      window.clearTimeout(this.scrollDebounceTimer);
    }

    // Set new timer
    this.scrollDebounceTimer = window.setTimeout(() => {
      console.debug('[AI-Slop] Processing posts after scroll');
      this.processExistingPosts().catch(error => {
        console.error('[AI-Slop] Error processing posts after scroll:', error);
      });
    }, this.SCROLL_DEBOUNCE_DELAY);
  }

  /**
   * Handles DOM mutations to detect and process new posts
   * @param mutations - Array of MutationRecord objects describing DOM changes
   */
  private handleMutations(mutations: MutationRecord[]): void {
    mutations.forEach(mutation => {
      mutation.addedNodes.forEach(node => {
        if (node instanceof HTMLElement) {
          // Process nodes asynchronously without blocking the mutation observer
          this.processNode(node).catch(error => {
            console.error('[AI-Slop] Error processing node:', error);
          });
        }
      });
    });
  }

  /**
   * Processes any posts that exist when the observer starts
   * Ensures posts loaded before observer initialization are processed
   * Updated to handle both article elements and group posts with enhanced timing resilience
   */
  private async processExistingPosts(): Promise<void> {
    // Early exit if not in an allowed group
    if (!this.isInAllowedGroup()) {
      return;
    }

    let validPostsFound = 0;
    let totalCandidatesScanned = 0;

    // Strategy 1: Query articles (regular feed posts)
    const articlePosts = document.querySelectorAll('[role="article"]');
    totalCandidatesScanned += articlePosts.length;

    for (const element of articlePosts) {
      if (element instanceof HTMLElement && this.isFacebookPost(element)) {
        validPostsFound++;
        await this.processPost(element);
      }
    }

    // Strategy 2: Look for Facebook feed containers with broader selectors
    const feedSelectors = [
      '[role="feed"] > div', // Feed container children
      '[data-pagelet*="FeedUnit"]', // Facebook feed units
      '[data-testid*="posts"]', // Posts with test IDs
      'div[style*="flex-direction: column"] > div', // Common Facebook layout pattern
    ];

    for (const selector of feedSelectors) {
      const feedElements = document.querySelectorAll(selector);
      totalCandidatesScanned += feedElements.length;

      for (const element of feedElements) {
        if (
          element instanceof HTMLElement &&
          !element.closest('[role="article"]') && // Avoid duplicates with articles
          this.isFacebookPost(element)
        ) {
          validPostsFound++;
          await this.processPost(element);
        }
      }
    }

    // Strategy 3: For Facebook groups, check for div elements with specific patterns
    // Look for containers with author headings and interaction buttons
    const groupPostCandidates = document.querySelectorAll('div');
    let groupPostsScanned = 0;

    for (const element of groupPostCandidates) {
      if (
        element instanceof HTMLElement &&
        element.querySelector('h2, h3, h4') && // Has author heading
        element.querySelectorAll('button').length > 3 && // Has multiple buttons (likely interactions)
        !element.closest('[role="article"]') && // Not already inside an article
        element.offsetHeight > 100 && // Must be reasonably tall (actual post content)
        element.offsetWidth > 300 // Must be reasonably wide
      ) {
        groupPostsScanned++;
        if (this.isFacebookPost(element)) {
          validPostsFound++;
          await this.processPost(element);
        }
      }
    }

    totalCandidatesScanned += groupPostsScanned;

    // Always log scan results to help debug timing issues
    console.log('[AI-Slop] 📈 Post scan complete:', {
      totalArticles: articlePosts.length,
      totalCandidatesScanned: totalCandidatesScanned,
      groupPostsScanned: groupPostsScanned,
      validPostsFound: validPostsFound,
      totalProcessed: this.processedPosts.size,
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Processes a DOM node to find and handle Facebook posts
   * Updated to handle both articles and group post structures
   * @param node - HTML element to process
   */
  private async processNode(node: HTMLElement): Promise<void> {
    // Early exit if not in an allowed group
    if (!this.isInAllowedGroup()) {
      return;
    }

    // Check if the node itself is a Facebook post
    if (this.isFacebookPost(node)) {
      await this.processPost(node);
      return;
    }

    // Check child nodes for article posts
    const potentialArticlePosts = node.querySelectorAll('[role="article"]');
    for (const element of potentialArticlePosts) {
      if (element instanceof HTMLElement && this.isFacebookPost(element)) {
        await this.processPost(element);
      }
    }

    // For group posts, check for div elements with post characteristics
    const potentialGroupPosts = node.querySelectorAll('div');
    for (const element of potentialGroupPosts) {
      if (
        element instanceof HTMLElement &&
        element.querySelector('h2, h3, h4') && // Has author heading
        element.querySelectorAll('button').length > 3 && // Has multiple buttons
        !element.closest('[role="article"]') && // Not inside an article
        this.isFacebookPost(element)
      ) {
        await this.processPost(element);
      }
    }
  }

  /**
   * Processes an individual Facebook post element
   * Adds AI slop detection functionality if not already processed
   * @param postElement - The post's HTML element
   */
  private async processPost(postElement: HTMLElement): Promise<void> {
    // Check if we're in an allowed group before processing
    if (!this.isInAllowedGroup()) {
      return;
    }

    // Generate unique ID for the post
    const postId = await this.generatePostId(postElement);

    if (this.processedPosts.has(postId)) {
      // Check if icon still exists
      const existingIcon = postElement.querySelector('.ai-slop-icon');
      if (existingIcon) {
        console.debug(`[AI-Slop] ⏭️ Post ${postId} already processed and icon exists, skipping`);
        return;
      } else {
        console.log(`[AI-Slop] 🔄 Post ${postId} was processed but icon missing, re-injecting`);
        // Remove from processed set to allow re-injection
        this.processedPosts.delete(postId);
      }
    }

    // Also check if the post already has a AI slop detection icon
    if (postElement.querySelector('.ai-slop-icon')) {
      console.debug(`[AI-Slop] ⏭️ Post already has icon, adding to processed set`);
      this.processedPosts.add(postId);
      return;
    }

    this.processedPosts.add(postId);
    console.log(`[AI-Slop] 🔄 Processing new post ${postId}:`, this.processedPosts.size);

    // Analyze post content with backend first, then inject icon
    await this.analyzeAndInjectIcon(postElement, postId);
  }

  /**
   * Analyzes post content (hardcoded for now) and injects icon with results
   * @param postElement - The post's HTML element
   * @param postId - Unique identifier for the post
   */
  private async analyzeAndInjectIcon(postElement: HTMLElement, postId: string): Promise<void> {
    try {
      // Extract post content
      const content = await this.extractPostContent(postElement);

      // Extract media URLs (images and videos)
      const mediaUrls = this.extractMediaUrls(postElement);

      // Process videos if any are found (using yt-dlp via backend)
      const videoResults: unknown[] = [];
      if (mediaUrls.hasVideos && mediaUrls.postUrl) {
        console.log(
          `[AI-Slop] Post ${postId} contains videos, will send post URL to backend for yt-dlp processing`
        );
        // Note: Video processing now happens in backend via yt-dlp
        // The post URL will be sent with the detection request
      }

      // Enhanced content validation to skip posts with repetitive content
      const trimmedContent = content.trim();
      const hasMedia = mediaUrls.images.length > 0 || mediaUrls.hasVideos;

      // Allow posts with no text content if they have media (media-only posts)
      if (trimmedContent.length === 0 && !hasMedia) {
        console.log(`[AI-Slop] ⏭️ Post ${postId} has no content and no media, skipping analysis`);
        return;
      }

      // For posts with text content, check for repetitive Facebook patterns
      if (trimmedContent.length > 0) {
        const facebookCount = (trimmedContent.toLowerCase().match(/(facebook)/gi) || []).length;
        const hasConsecutiveFacebook = trimmedContent.toLowerCase().match(/(facebook){3,}/gi);
        const facebookRatio =
          trimmedContent.length > 0 ? facebookCount / (trimmedContent.length / 8) : 0; // Rough word ratio

        const isInvalidTextContent =
          trimmedContent.length < 10 ||
          hasConsecutiveFacebook ||
          (facebookCount > 10 && facebookRatio > 0.3); // Too many Facebook occurrences

        if (isInvalidTextContent) {
          console.log(
            `[AI-Slop] ⏭️ Post ${postId} has repetitive text content (${trimmedContent.length} chars, ${facebookCount} "Facebook" occurrences), skipping analysis`
          );
          return;
        }
      }

      console.log(`[AI-Slop] 🔍 Analyzing post ${postId} with backend API...`);

      // Send analysis request to backend via background service
      const response = await new Promise<{
        isAiSlop: boolean;
        confidence: number;
        reasoning: string;
        textAiProbability?: number;
        textConfidence?: number;
        imageAiProbability?: number;
        imageConfidence?: number;
        videoAiProbability?: number;
        videoConfidence?: number;
        analysisDetails: Record<string, unknown>;
        processingTime: number;
        timestamp: string;
      }>((resolve, reject) => {
        chrome.runtime.sendMessage(
          {
            type: 'AI_SLOP_REQUEST',
            content: content,
            postId: postId,
            imageUrls: mediaUrls.images,
            videoUrls: mediaUrls.videos, // Keep empty for compatibility
            postUrl: mediaUrls.postUrl,
            hasVideos: mediaUrls.hasVideos,
            videoResults: videoResults,
          },
          response => {
            if (chrome.runtime.lastError) {
              console.error('[AI-Slop] ❌ Runtime error:', chrome.runtime.lastError);
              reject(chrome.runtime.lastError);
            } else if (response && response.error) {
              console.error('[AI-Slop] ❌ API error:', response.error);
              reject(new Error(response.error));
            } else {
              console.log('[AI-Slop] ✅ Analysis response received:', response);
              resolve(response);
            }
          }
        );
      });

      console.log(`[AI-Slop] ✅ Hardcoded analysis complete for post ${postId}:`, {
        isAiSlop: response.isAiSlop,
        confidence: response.confidence,
      });

      // Store analysis result and inject icon
      this.injectFactCheckIcon(postElement, postId, content, response);
    } catch (error) {
      console.error(`[AI-Slop] ❌ Error analyzing post ${postId}:`, error);
      // Don't show icon if analysis fails to avoid confusion
    }
  }

  /**
   * Generates a unique ID for a post based on Facebook's URL structure
   * Priority: URL-based ID > content-based fallback > DOM-based fallback
   * @param postElement - The post's HTML element
   * @returns Facebook post ID (numeric string) or fallback Base64 encoded string
   */
  private async generatePostId(postElement: HTMLElement): Promise<string> {
    // Primary method: Extract post ID from Facebook URLs with retry logic
    const postId = await this.extractPostIdFromUrls(postElement);
    if (postId) {
      console.log(`[AI-Slop] 🆔 Using URL-based post ID: ${postId}`);
      return postId;
    }

    console.log(`[AI-Slop] ⚠️ No URL-based ID found, falling back to legacy method`);

    // Fallback to legacy content/DOM-based ID generation
    const content = await this.extractPostContent(postElement);

    // Get additional unique characteristics from the DOM
    const authorElement = postElement.querySelector('h2, h3, h4');
    const authorText = authorElement?.textContent?.trim().slice(0, 50) || '';

    // Get timestamp or date links
    const timeElement = postElement.querySelector(
      'a[href*="posts/"], time, [aria-label*="ago"], [aria-label*="hours"], [aria-label*="minutes"]'
    );
    const timeText = timeElement?.textContent?.trim().slice(0, 30) || '';
    const timeHref = timeElement?.getAttribute('href')?.slice(0, 50) || '';

    // Get the element's position in the DOM (as a fallback identifier)
    const position = Array.from(document.querySelectorAll('*')).indexOf(postElement);

    // Check if content is generic (Facebook repetition pattern)
    const isGenericContent =
      content.length > 200 &&
      (content.toLowerCase().includes('facebook'.repeat(10)) ||
        (content.toLowerCase().match(/(facebook)/gi) || []).length > 15 || // Too many "Facebook" occurrences
        content.toLowerCase().match(/(facebook){5,}/gi)); // Consecutive "Facebook" repetitions

    let uniqueString: string;

    if (isGenericContent || content.length < 20) {
      // Use DOM-based identification for posts with poor content extraction
      uniqueString = `${authorText}-${timeText}-${timeHref}-${position}-${postElement.className}-${Date.now()}`;
      console.log(`[AI-Slop] 🆔 Using DOM-based ID for post with generic content`);
    } else {
      // Use content-based identification for posts with good content
      uniqueString = `${content.slice(0, 100)}-${authorText}`;
    }

    try {
      return btoa(encodeURIComponent(uniqueString));
    } catch (error) {
      // Ultimate fallback
      const fallbackId = `${Date.now()}-${Math.random()}-${position}`;
      console.warn(`[AI-Slop] ⚠️ Using fallback ID generation:`, error);
      return btoa(fallbackId);
    }
  }

  /**
   * Extracts Facebook post ID from URLs within the post element with retry logic
   * Looks for patterns like /posts/{numeric_id} or /posts/{numeric_id}/
   * @param postElement - The post's HTML element
   * @param retryCount - Number of retries attempted (default: 0)
   * @returns Facebook post ID (numeric string) or null if not found
   */
  private async extractPostIdFromUrls(
    postElement: HTMLElement,
    retryCount: number = 0
  ): Promise<string | null> {
    const maxRetries = 3;
    const retryDelay = 200; // 200ms between retries

    // Look for all links within the post that might contain post IDs
    // Check multiple patterns to catch various Facebook URL formats
    const linkSelectors = [
      'a[href*="posts/"]',
      'a[href*="/posts/"]',
      'a[href*="story_fbid="]',
      'a[href*="fbid="]',
      'time a',
      '[aria-label*="ago"] a',
      '[aria-label*="hours"] a',
      '[aria-label*="minutes"] a',
    ];

    const allLinks = new Set<HTMLAnchorElement>();

    // Collect all potential links
    linkSelectors.forEach(selector => {
      const links = postElement.querySelectorAll(selector);
      links.forEach(link => {
        if (link instanceof HTMLAnchorElement) {
          allLinks.add(link);
        }
      });
    });

    for (const link of allLinks) {
      const href = link.getAttribute('href') || '';

      if (!href) continue;

      // Try different Facebook URL patterns:

      // Pattern 1: /posts/{numeric_id}
      let match = href.match(/\/posts\/(\d+)/);
      if (match && match[1]) {
        const postId = match[1];
        console.log(
          `[AI-Slop] 🔗 Extracted post ID from URL (posts pattern): ${postId} (from: ${href.slice(0, 100)}...)`
        );
        return postId;
      }

      // Pattern 2: story_fbid={numeric_id}
      match = href.match(/story_fbid=(\d+)/);
      if (match && match[1]) {
        const postId = match[1];
        console.log(
          `[AI-Slop] 🔗 Extracted post ID from URL (story_fbid pattern): ${postId} (from: ${href.slice(0, 100)}...)`
        );
        return postId;
      }

      // Pattern 3: fbid={numeric_id}
      match = href.match(/fbid=(\d+)/);
      if (match && match[1]) {
        const postId = match[1];
        console.log(
          `[AI-Slop] 🔗 Extracted post ID from URL (fbid pattern): ${postId} (from: ${href.slice(0, 100)}...)`
        );
        return postId;
      }

      // Pattern 4: /{numeric_id}/posts/{another_id} (group posts)
      match = href.match(/\/(\d{10,})\/posts\/(\d+)/);
      if (match && match[2]) {
        const postId = match[2];
        console.log(
          `[AI-Slop] 🔗 Extracted post ID from URL (group posts pattern): ${postId} (from: ${href.slice(0, 100)}...)`
        );
        return postId;
      }
    }

    // If no URLs found and we haven't exceeded retry limit, wait and try again
    if (retryCount < maxRetries) {
      console.log(
        `[AI-Slop] 🔄 No post URLs found (attempt ${retryCount + 1}/${maxRetries + 1}), retrying in ${retryDelay}ms...`
      );
      await new Promise(resolve => setTimeout(resolve, retryDelay));
      return this.extractPostIdFromUrls(postElement, retryCount + 1);
    }

    console.log(
      `[AI-Slop] 🔍 No post URLs found after ${maxRetries + 1} attempts, checked ${allLinks.size} links`
    );
    return null;
  }

  /**
   * Extracts text content from a Facebook post
   * Enhanced to handle both regular feed posts and Facebook group posts
   * Automatically expands collapsed posts by clicking "See more" buttons
   * @param postElement - The post's HTML element
   * @returns Post text content or empty string if not found
   */
  private async extractPostContent(postElement: HTMLElement): Promise<string> {
    let content = '';
    let extractionMethod = '';

    // First, check for and click "See more" buttons to expand collapsed content
    await this.expandCollapsedContent(postElement);

    // Try multiple selectors for content extraction
    // 1. Primary selector for post content
    let contentElement = postElement.querySelector(this.POST_CONTENT_SELECTOR);

    if (contentElement) {
      content = contentElement.textContent || '';
      extractionMethod = 'data-ad-comet-preview="message"';
    } else {
      // 2. Fallback to other potential content selectors
      contentElement = postElement.querySelector('[data-ad-preview="message"]');
      if (contentElement) {
        content = contentElement.textContent || '';
        extractionMethod = 'data-ad-preview="message"';
      }
    }

    // 3. If no content found with primary selectors, leave it empty
    // Posts without text content (media-only posts) should have empty content
    // and rely on media analysis in the backend

    // Clean up the content
    content = content.trim().replace(/\s+/g, ' ');

    // Log extraction results
    console.log('[AI-Slop] 📄 Content extracted:', {
      method: extractionMethod,
      length: content.length,
      preview: content.substring(0, 150) + (content.length > 150 ? '...' : ''),
    });

    if (content.length === 0) {
      console.warn('[AI-Slop] ⚠️ No content extracted from post!');
    }

    return content;
  }

  /**
   * Extracts image and video URLs from a Facebook post
   * @param postElement - The post's HTML element
   * @returns Object containing arrays of image and video URLs
   */
  private extractMediaUrls(postElement: HTMLElement): {
    images: string[];
    videos: string[];
    postUrl?: string;
    hasVideos: boolean;
  } {
    const images: string[] = [];

    // Extract image URLs
    // Facebook images are typically in img tags with data-src or src attributes
    const imageElements = postElement.querySelectorAll('img');
    imageElements.forEach(img => {
      // Skip small images (likely icons or avatars)
      if (img.width > 100 || img.height > 100 || (!img.width && !img.height)) {
        // Skip images that are part of video elements (video thumbnails/posters)
        const isVideoThumbnail =
          img.closest('video') ||
          img.closest('[data-video-id]') ||
          img.closest('[role="button"][aria-label*="video"]') ||
          img.closest('[role="button"][aria-label*="Video"]') ||
          img.closest('[role="button"][aria-label*="Play"]') ||
          img.closest('[data-testid*="video"]') ||
          img.closest('.videoContainer') ||
          img.closest('[class*="video"]') ||
          img.getAttribute('data-video') ||
          img.hasAttribute('poster') ||
          // Check if parent post contains video controls/elements
          postElement.querySelector('button[aria-label*="Play video"]') ||
          postElement.querySelector('button[aria-label*="Play"]') ||
          postElement.querySelector('video') ||
          postElement.querySelector('[data-testid*="video"]');

        if (isVideoThumbnail) {
          console.log(
            '[AI-Slop] 🎬 Skipping video thumbnail/poster image:',
            img.src?.substring(0, 100)
          );
          return;
        }

        const src = img.getAttribute('src') || img.getAttribute('data-src');
        if (src && !src.includes('emoji') && !src.includes('icon') && !src.includes('avatar')) {
          // Skip Facebook video thumbnail URLs (pattern: t15.xxxx-xx)
          if (src.includes('t15.') && src.includes('-10/')) {
            console.log(
              '[AI-Slop] 🎬 Skipping Facebook video thumbnail by URL pattern:',
              src.substring(0, 100)
            );
            return;
          }

          // Don't clean Facebook URLs - preserve all authentication parameters
          if (!images.includes(src)) {
            images.push(src);
          }
        }
      }
    });

    // Also check for background images in divs (Facebook sometimes uses these)
    const divElements = postElement.querySelectorAll('div[style*="background-image"]');
    divElements.forEach(div => {
      // Skip background images that are part of video elements
      const isVideoThumbnail =
        div.closest('video') ||
        div.closest('[data-video-id]') ||
        div.closest('[role="button"][aria-label*="video"]') ||
        div.closest('[role="button"][aria-label*="Video"]') ||
        div.closest('[role="button"][aria-label*="Play"]') ||
        div.closest('[data-testid*="video"]') ||
        div.closest('.videoContainer') ||
        div.closest('[class*="video"]') ||
        div.getAttribute('data-video') ||
        // Check if parent post contains video controls/elements
        postElement.querySelector('button[aria-label*="Play video"]') ||
        postElement.querySelector('button[aria-label*="Play"]') ||
        postElement.querySelector('video') ||
        postElement.querySelector('[data-testid*="video"]');

      if (isVideoThumbnail) {
        console.log('[AI-Slop] 🎬 Skipping video background image');
        return;
      }

      const style = div.getAttribute('style') || '';
      const match = style.match(/url\(["']?([^"')]+)["']?\)/);
      if (match && match[1]) {
        // Don't clean Facebook URLs - preserve all authentication parameters
        if (!images.includes(match[1])) {
          images.push(match[1]);
        }
      }
    });

    // Check if post contains videos (don't extract blob URLs anymore)
    const videoElements = postElement.querySelectorAll('video');
    const hasVideos = videoElements.length > 0;
    let postUrl: string | undefined;

    // If post has videos, extract post URL for yt-dlp downloading
    if (hasVideos) {
      // Try to find post permalink
      const postLinks = postElement.querySelectorAll(
        'a[href*="/reel/"], a[href*="/watch/"], a[href*="/videos/"], a[href*="/posts/"], a[role="link"][href*="facebook.com"]'
      );

      for (const link of postLinks) {
        const href = (link as HTMLAnchorElement).href;
        // Look for timestamps or "Full Story" links which are usually permalinks
        const linkText = link.textContent?.toLowerCase() || '';
        if (
          linkText.includes('full story') ||
          linkText.includes('min') ||
          linkText.includes('hr') ||
          linkText.includes('yesterday') ||
          linkText.includes('ago')
        ) {
          postUrl = href;
          break;
        }
      }

      // Fallback: try to construct URL from current page if we're on a post page
      if (
        !postUrl &&
        (window.location.href.includes('/posts/') || window.location.href.includes('/videos/'))
      ) {
        postUrl = window.location.href;
      }

      // Last resort: look for any link that might be the post
      if (!postUrl && postLinks.length > 0) {
        postUrl = (postLinks[0] as HTMLAnchorElement).href;
      }

      console.log('[AI-Slop] 🎥 Found video in post, extracted post URL:', postUrl);
    }

    // Note: We no longer extract video blob URLs as they can't be downloaded by backend
    // Instead, we send the post URL for yt-dlp to handle

    console.log('[AI-Slop] 📸 Extracted media info:', {
      images: images.length,
      hasVideos,
      postUrl: postUrl?.substring(0, 100),
    });

    return { images, videos: [], postUrl, hasVideos };
  }

  /**
   * Expands collapsed content by finding and clicking "See more" buttons
   * Handles various Facebook "See more" button patterns and waits for content expansion
   * @param postElement - The post's HTML element
   */
  private async expandCollapsedContent(postElement: HTMLElement): Promise<void> {
    // Find "See more" buttons using text content matching
    const findSeeMoreButton = (): HTMLElement | null => {
      // Check all potential buttons in the post
      const buttons = postElement.querySelectorAll(
        'div[role="button"], span[role="button"], [role="button"]'
      );

      for (const button of buttons) {
        const text = button.textContent?.trim().toLowerCase();
        if (text === 'see more' || text === 'see more.' || text === '... see more') {
          return button as HTMLElement;
        }
      }

      // Also check for span elements that might contain "See more" text
      const spans = postElement.querySelectorAll('span');
      for (const span of spans) {
        const text = span.textContent?.trim().toLowerCase();
        if (text === 'see more' || text === 'see more.' || text === '... see more') {
          // Check if the span or its parent is clickable
          const clickableParent = span.closest(
            '[role="button"], div[style*="cursor"], span[style*="cursor"]'
          );
          if (clickableParent) {
            return clickableParent as HTMLElement;
          }
          return span as HTMLElement;
        }
      }

      // Look for ellipsis followed by "See more" pattern
      const allElements = postElement.querySelectorAll('*');
      for (const element of allElements) {
        const text = element.textContent?.trim();
        if (
          text &&
          (text.includes('...See more') ||
            text.includes('… See more') ||
            text.endsWith('... See more'))
        ) {
          return element as HTMLElement;
        }
      }

      return null;
    };

    let attempts = 0;
    const maxAttempts = 3;

    while (attempts < maxAttempts) {
      const seeMoreButton = findSeeMoreButton();

      if (!seeMoreButton) {
        console.debug('[AI-Slop] 📄 No "See more" button found in post');
        break;
      }

      console.log('[AI-Slop] 🔍 Found "See more" button, expanding content...');

      // Store the current content length to detect if expansion worked
      const beforeContent = postElement.textContent?.length || 0;

      try {
        // Click the "See more" button
        if (seeMoreButton.click) {
          seeMoreButton.click();
        } else {
          // Fallback: dispatch click event
          const clickEvent = new MouseEvent('click', {
            bubbles: true,
            cancelable: true,
            view: window,
          });
          seeMoreButton.dispatchEvent(clickEvent);
        }

        // Wait for content to expand
        await new Promise(resolve => setTimeout(resolve, 500));

        // Check if content expanded
        const afterContent = postElement.textContent?.length || 0;
        const expansionOccurred = afterContent > beforeContent;

        if (expansionOccurred) {
          console.log('[AI-Slop] ✅ Content expanded successfully', {
            beforeLength: beforeContent,
            afterLength: afterContent,
            expanded: afterContent - beforeContent,
          });

          // Wait a bit more for any additional content loading
          await new Promise(resolve => setTimeout(resolve, 200));
          break;
        } else {
          console.log('[AI-Slop] ⚠️ Content expansion may not have worked, retrying...');
          attempts++;
        }
      } catch (error) {
        console.warn('[AI-Slop] ⚠️ Error clicking "See more" button:', error);
        attempts++;
      }
    }

    if (attempts >= maxAttempts) {
      console.log('[AI-Slop] ⏹️ Reached maximum expansion attempts');
    }
  }

  /**
   * Injects the AI slop detection icon into a Facebook post with analysis results
   * Creates and adds the interactive icon element with enhanced targeting
   * @param postElement - The post's HTML element
   * @param postId - Unique identifier for the post used for logging and debugging
   * @param content - The extracted post content
   * @param analysisResult - The AI slop analysis result from backend
   */
  private injectFactCheckIcon(
    postElement: HTMLElement,
    postId: string,
    content: string,
    analysisResult: {
      isAiSlop: boolean;
      confidence: number;
      reasoning: string;
      textAiProbability?: number;
      textConfidence?: number;
      imageAiProbability?: number;
      imageConfidence?: number;
      videoAiProbability?: number;
      videoConfidence?: number;
      analysisDetails?: Record<string, unknown>;
      processingTime: number;
      timestamp: string;
    }
  ): void {
    console.log(`[AI-Slop] 🎯 Starting icon injection for post: ${postId}`);

    // Create the AI slop detection icon button
    const iconContainer = document.createElement('div');
    iconContainer.className = 'ai-slop-icon';
    iconContainer.setAttribute('data-post-id', postId);
    iconContainer.setAttribute('data-content', content);
    iconContainer.setAttribute('data-analysis', JSON.stringify(analysisResult));
    iconContainer.setAttribute('data-state', 'analyzed');

    // Set icon based on analysis result
    const isAiSlop = analysisResult.isAiSlop;

    if (isAiSlop) {
      // AI slop detected - yellow warning triangle
      iconContainer.innerHTML = `
        <svg viewBox="0 0 24 24" width="20" height="20">
          <path d="M12 2 L22 20 L2 20 Z" fill="#FFC107" stroke="#F57C00" stroke-width="1"/>
          <text x="12" y="16" font-family="Arial, sans-serif" font-size="10" font-weight="bold" text-anchor="middle" fill="#5D4037">!</text>
        </svg>
      `;
      iconContainer.setAttribute('title', 'AI-generated content detected - Click to open chat');
    } else {
      // Human content - green checkmark
      iconContainer.innerHTML = `
        <svg viewBox="0 0 24 24" width="20" height="20">
          <circle cx="12" cy="12" r="10" fill="#4CAF50" stroke="#388E3C" stroke-width="1"/>
          <path d="M7 12.5 L10 15.5 L17 8.5" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
        </svg>
      `;
      iconContainer.setAttribute('title', 'Human-generated content - Click to open chat');
    }

    // Add click handler to open chat directly
    iconContainer.addEventListener('click', () =>
      this.openChatForPost(postElement, postId, content, analysisResult)
    );

    // Enhanced targeting for Facebook group posts
    let targetElement: HTMLElement | null = null;
    let injectionMethod = '';

    // Strategy 1: Find author heading and use its parent
    const authorContainer = postElement.querySelector('h2, h3, h4');
    if (authorContainer && authorContainer.parentElement instanceof HTMLElement) {
      targetElement = authorContainer.parentElement;
      injectionMethod = 'Author parent container';
    }

    // Strategy 2: Find any element with author links (profile links)
    if (!targetElement) {
      const authorLink = postElement.querySelector('a[href*="/user/"], a[href*="/profile/"]');
      if (authorLink && authorLink.parentElement instanceof HTMLElement) {
        // Go up the tree to find a suitable container
        let parent: HTMLElement | null = authorLink.parentElement;
        let depth = 0;
        while (parent && depth < 5) {
          // Look for a container that's likely the post header
          if (parent.offsetWidth > 100 && parent.offsetHeight > 20) {
            targetElement = parent;
            injectionMethod = 'Author link container';
            break;
          }
          parent = parent.parentElement instanceof HTMLElement ? parent.parentElement : null;
          depth++;
        }
      }
    }

    // Strategy 3: Find elements containing timestamps or "shared with" text
    if (!targetElement) {
      const timestampElement = postElement.querySelector(
        'a[href*="posts/"], [aria-label*="ago"], [aria-label*="hours"], [aria-label*="minutes"]'
      );
      if (timestampElement && timestampElement.parentElement instanceof HTMLElement) {
        // Go up to find a container
        let parent: HTMLElement | null = timestampElement.parentElement;
        let depth = 0;
        while (parent && depth < 3) {
          if (parent.offsetWidth > 200) {
            targetElement = parent;
            injectionMethod = 'Timestamp container';
            break;
          }
          parent = parent.parentElement instanceof HTMLElement ? parent.parentElement : null;
          depth++;
        }
      }
    }

    // Strategy 4: Look for any relatively positioned containers in the upper part
    if (!targetElement) {
      const containers = postElement.querySelectorAll('div');
      for (const container of containers) {
        if (container instanceof HTMLElement) {
          const rect = container.getBoundingClientRect();
          const postRect = postElement.getBoundingClientRect();

          // Check if this container is in the upper part of the post
          if (rect.top <= postRect.top + 80 && rect.width > 200 && rect.height > 30) {
            targetElement = container;
            injectionMethod = 'Upper container';
            break;
          }
        }
      }
    }

    // Strategy 5: Use the first substantial child element as last resort
    if (!targetElement) {
      const firstChild = postElement.firstElementChild;
      if (firstChild instanceof HTMLElement && firstChild.offsetWidth > 100) {
        targetElement = firstChild;
        injectionMethod = 'First child container';
      }
    }

    // Strategy 6: Ultimate fallback - use the post element itself
    if (!targetElement) {
      targetElement = postElement;
      injectionMethod = 'Post element (fallback)';
    }

    if (targetElement) {
      // Check if icon already exists anywhere in the post
      const existingIcon = postElement.querySelector('.ai-slop-icon');
      if (existingIcon) {
        console.warn(`[AI-Slop] ⚠️ Icon already exists for post ${postId}, skipping injection`);
        return;
      }

      console.log(`[AI-Slop] 🎯 Target element found via: ${injectionMethod}`, targetElement);

      // Style the icon container with professional styling and maximum visibility
      iconContainer.style.cssText = `
        position: absolute !important;
        top: 10px !important;
        right: 10px !important;
        cursor: pointer !important;
        z-index: 2147483647 !important;
        background: #ffffff !important;
        border-radius: 50% !important;
        padding: 6px !important;
        box-shadow: 0 3px 10px rgba(0,0,0,0.3) !important;
        width: 36px !important;
        height: 36px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        border: 2px solid #1877f2 !important;
        opacity: 1 !important;
        visibility: visible !important;
        pointer-events: auto !important;
        transform: scale(1) !important;
        overflow: visible !important;
        clip: unset !important;
        clip-path: none !important;
        max-width: none !important;
        max-height: none !important;
        min-width: 36px !important;
        min-height: 36px !important;
        transition: all 0.2s ease !important;
      `;

      // Make parent position relative if needed
      const currentPosition = getComputedStyle(targetElement).position;
      if (currentPosition === 'static') {
        targetElement.style.position = 'relative';
        console.log(`[AI-Slop] 📍 Set target element position to relative`);
      }

      try {
        targetElement.appendChild(iconContainer);
        console.log(
          `[AI-Slop] ✅ Icon injected successfully for post ${postId} via ${injectionMethod}`
        );
      } catch (error) {
        console.error(`[AI-Slop] ❌ Failed to append icon for post ${postId}:`, error);
      }
    } else {
      console.error(
        `[AI-Slop] ❌ Failed to find suitable element for icon injection for post ${postId}`
      );

      // Add debug information about the post structure
      console.log(`[AI-Slop] 🔍 Post element structure for debugging:`, {
        tagName: postElement.tagName,
        className: postElement.className,
        hasAuthorHeading: !!postElement.querySelector('h2, h3, h4'),
        buttonCount: postElement.querySelectorAll('button').length,
        childrenCount: postElement.children.length,
        offsetDimensions: {
          width: postElement.offsetWidth,
          height: postElement.offsetHeight,
        },
      });
    }
  }

  /**
   * Opens the chat overlay for a post with pre-analyzed results
   * @param postElement - The post's HTML element
   * @param postId - Unique identifier for the post
   * @param content - The extracted post content
   * @param analysisResult - The AI slop analysis result
   */
  private openChatForPost(
    postElement: HTMLElement,
    postId: string,
    content: string,
    analysisResult: {
      isAiSlop: boolean;
      confidence: number;
      reasoning: string;
      textAiProbability?: number;
      textConfidence?: number;
      imageAiProbability?: number;
      imageConfidence?: number;
      videoAiProbability?: number;
      videoConfidence?: number;
      analysisDetails?: Record<string, unknown>;
      processingTime: number;
      timestamp: string;
    }
  ): void {
    console.log(`[AI-Slop] 💬 Opening chat for post ${postId}`);

    // Check if a chat window for this post already exists
    const existingChat = document.querySelector(`.detect-chat-window[data-post-id="${postId}"]`);
    if (existingChat) {
      // Bring existing chat to front
      (existingChat as HTMLElement).style.zIndex = String(2147483647 + (Date.now() % 100));
      // Flash the header to indicate it's already open
      const header = existingChat.querySelector('.chat-window-header') as HTMLElement;
      if (header) {
        header.style.backgroundColor = '#e3f2fd !important';
        setTimeout(() => {
          header.style.backgroundColor = '#f9fafb !important';
        }, 300);
      }
      return;
    }

    this.showChatOverlay(postElement, postId, content, analysisResult);
  }

  /**
   * Updates the AI slop detection icon's visual state
   * @param postElement - The post's HTML element
   * @param state - Current state of the analysis process
   * @param isAiSlop - Whether the content is AI slop (for analyzed state)
   */
  private updateIconState(
    postElement: HTMLElement,
    state: 'loading' | 'error' | 'analyzed',
    isAiSlop?: boolean
  ): void {
    const icon = postElement.querySelector('.ai-slop-icon');
    if (icon) {
      icon.setAttribute('data-state', state);

      // Update icon appearance based on state
      const iconElement = icon as HTMLElement;
      if (state === 'loading') {
        iconElement.innerHTML = `
          <svg viewBox="0 0 24 24" width="20" height="20">
            <circle cx="12" cy="12" r="10" fill="none" stroke="#1877f2" stroke-width="2" opacity="0.3"/>
            <path fill="#1877f2" d="M12 2a10 10 0 0 1 10 10h-2a8 8 0 0 0-8-8V2z">
              <animateTransform attributeName="transform" type="rotate" values="0 12 12;360 12 12" dur="1s" repeatCount="indefinite"/>
            </path>
          </svg>`;
        iconElement.setAttribute('title', 'Analyzing content...');
      } else if (state === 'error') {
        iconElement.innerHTML = `
          <svg viewBox="0 0 24 24" width="20" height="20">
            <circle cx="12" cy="12" r="10" fill="#e74c3c" stroke="#c0392b" stroke-width="1"/>
            <text x="12" y="17" font-family="Arial, sans-serif" font-size="14" font-weight="bold" text-anchor="middle" fill="white">!</text>
          </svg>`;
        iconElement.setAttribute('title', 'Error analyzing content');
      } else if (state === 'analyzed' && isAiSlop !== undefined) {
        if (isAiSlop) {
          // AI slop detected - yellow warning triangle
          iconElement.innerHTML = `
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path d="M12 2 L22 20 L2 20 Z" fill="#FFC107" stroke="#F57C00" stroke-width="1"/>
              <text x="12" y="16" font-family="Arial, sans-serif" font-size="10" font-weight="bold" text-anchor="middle" fill="#5D4037">!</text>
            </svg>`;
          iconElement.setAttribute('title', 'AI-generated content detected');
        } else {
          // Human content - green checkmark
          iconElement.innerHTML = `
            <svg viewBox="0 0 24 24" width="20" height="20">
              <circle cx="12" cy="12" r="10" fill="#4CAF50" stroke="#388E3C" stroke-width="1"/>
              <path d="M7 12.5 L10 15.5 L17 8.5" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>`;
          iconElement.setAttribute('title', 'Human-generated content');
        }
      }
    }
  }

  /**
   * Generates confidence display HTML with separate values for text, image, and video
   * Only shows sections for content types that are actually present in the post
   */
  private generateConfidenceDisplay(
    analysisResult: {
      confidence: number;
      textAiProbability?: number;
      textConfidence?: number;
      imageAiProbability?: number;
      imageConfidence?: number;
      videoAiProbability?: number;
      videoConfidence?: number;
    },
    contentPresent: {
      hasText: boolean;
      hasImages: boolean;
      hasVideos: boolean;
    }
  ): string {
    const sections = [];

    // Show text analysis only if post has text content AND analysis values are available
    if (
      contentPresent.hasText &&
      analysisResult.textAiProbability !== undefined &&
      analysisResult.textConfidence !== undefined
    ) {
      sections.push(`
        <div class="modality-analysis">
          <strong>📝 Text:</strong> 
          ${Math.round(analysisResult.textAiProbability * 100)}% AI probability, 
          ${Math.round(analysisResult.textConfidence * 100)}% confidence
        </div>
      `);
    }

    // Show image analysis only if post has images AND analysis values are available
    if (
      contentPresent.hasImages &&
      analysisResult.imageAiProbability !== undefined &&
      analysisResult.imageConfidence !== undefined
    ) {
      sections.push(`
        <div class="modality-analysis">
          <strong>🖼️ Images:</strong> 
          ${Math.round(analysisResult.imageAiProbability * 100)}% AI probability, 
          ${Math.round(analysisResult.imageConfidence * 100)}% confidence
        </div>
      `);
    }

    // Show video analysis only if post has videos AND analysis values are available
    if (
      contentPresent.hasVideos &&
      analysisResult.videoAiProbability !== undefined &&
      analysisResult.videoConfidence !== undefined
    ) {
      sections.push(`
        <div class="modality-analysis">
          <strong>🎥 Videos:</strong> 
          ${Math.round(analysisResult.videoAiProbability * 100)}% AI probability, 
          ${Math.round(analysisResult.videoConfidence * 100)}% confidence
        </div>
      `);
    }

    // Fallback to legacy confidence if no separate values are available
    if (sections.length === 0) {
      return `Overall Confidence: ${Math.round(analysisResult.confidence * 100)}%`;
    }

    return sections.join('');
  }

  /**
   * Creates and displays the chat window for AI slop analysis (non-blocking)
   * @param postElement - The post's HTML element
   * @param postId - Unique identifier for the post
   * @param postContent - The extracted post content
   * @param analysisResult - The AI slop analysis result
   */
  private showChatOverlay(
    postElement: HTMLElement,
    postId: string,
    postContent: string,
    analysisResult: {
      isAiSlop: boolean;
      confidence: number;
      reasoning: string;
      textAiProbability?: number;
      textConfidence?: number;
      imageAiProbability?: number;
      imageConfidence?: number;
      videoAiProbability?: number;
      videoConfidence?: number;
      analysisDetails?: Record<string, unknown>;
      processingTime: number;
      timestamp: string;
    }
  ): void {
    // Count existing chat windows to position new ones appropriately
    const existingWindows = document.querySelectorAll('.detect-chat-window');
    const windowCount = existingWindows.length;
    const offset = windowCount * 30; // Cascade windows

    // Determine what content types are present in the post
    const mediaUrls = this.extractMediaUrls(postElement);
    const contentPresent = {
      hasText: Boolean(postContent && postContent.trim().length > 0),
      hasImages: mediaUrls.images.length > 0,
      hasVideos: mediaUrls.hasVideos,
    };

    const chatWindow = document.createElement('div');
    chatWindow.className = 'detect-chat-window';
    chatWindow.setAttribute('data-post-id', postId);

    // Position the new window with cascade effect
    chatWindow.style.top = `${20 + offset}px`;
    chatWindow.style.right = `${20 + offset}px`;

    // Extract author information
    const authorElement = postElement.querySelector('h2, h3, h4');
    const authorText = authorElement?.textContent?.trim() || 'Unknown User';

    // Clean up author text and add @ prefix
    const username = authorText.split('\n')[0].trim(); // Take first line only
    const formattedUsername = username.startsWith('@') ? username : `@${username}`;

    // Check if content is meaningful (not generic Facebook UI text)
    const isGenericContent =
      !postContent.trim() ||
      postContent.length < 10 ||
      postContent.toLowerCase().includes('facebook'.repeat(5)) ||
      (postContent.toLowerCase().match(/(facebook)/gi) || []).length > 10 || // Too many "Facebook" occurrences
      postContent.toLowerCase().match(/(facebook){3,}/gi) || // Consecutive "Facebook" repetitions
      postContent.toLowerCase().includes('like comment share') ||
      /^[\s\n]*$/.test(postContent); // Only whitespace/newlines

    // Extract a preview of the post content for the subtitle
    let subtitle = formattedUsername;
    if (!isGenericContent) {
      const contentPreview =
        postContent.trim().substring(0, 100) + (postContent.length > 100 ? '...' : '');
      subtitle = `${formattedUsername} - ${contentPreview}`;
    }

    chatWindow.innerHTML = `
      <div class="chat-window-header">
        <div class="chat-window-title">
          <div class="chat-window-icon">
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
          </div>
          <div class="title-text">
            <span class="title-main">AI Content Analysis</span>
            <span class="title-preview" title="${postContent}">${subtitle}</span>
          </div>
        </div>
        <div class="chat-window-controls">
          <button class="minimize-chat" title="Minimize">−</button>
          <button class="close-chat" title="Close">&times;</button>
        </div>
      </div>
      
      <div class="analysis-result ${analysisResult.isAiSlop ? 'ai-detected' : 'human-content'}">
        <div class="verdict">
          <strong>${analysisResult.isAiSlop ? '🤖 AI-Generated Content Detected' : '👤 Human-Generated Content'}</strong>
        </div>
        <div class="confidence">
          ${this.generateConfidenceDisplay(analysisResult, contentPresent)}
        </div>
        <div class="reasoning">
          ${analysisResult.reasoning}
        </div>
        <button class="ignore-analysis" ${analysisResult.isAiSlop ? '' : 'style="display: none;"'}>
          Ignore This Analysis
        </button>
      </div>

      <div class="chat-messages">
        <div class="system-message">
          Ask me anything about this analysis or the post content!
        </div>
      </div>

      <div class="chat-input-container">
        <input type="text" class="chat-input" placeholder="Ask about this analysis..." />
        <button class="send-chat">Send</button>
      </div>
    `;

    // Store analysis data for chat context
    chatWindow.setAttribute('data-post-content', postContent);
    chatWindow.setAttribute('data-analysis', JSON.stringify(analysisResult));

    // Add event listeners
    this.setupChatWindowEventListeners(chatWindow);

    document.body.appendChild(chatWindow);

    // Load previous chat history for this user and post
    this.loadChatHistory(chatWindow, postId);
  }

  /**
   * Sets up event listeners for the chat window
   * @param chatWindow - The chat window element
   */
  private setupChatWindowEventListeners(chatWindow: HTMLElement): void {
    const closeButton = chatWindow.querySelector('.close-chat');
    const minimizeButton = chatWindow.querySelector('.minimize-chat');
    const chatInput = chatWindow.querySelector('.chat-input') as HTMLInputElement;
    const sendButton = chatWindow.querySelector('.send-chat');
    const ignoreButton = chatWindow.querySelector('.ignore-analysis');

    // Close chat window
    closeButton?.addEventListener('click', () => chatWindow.remove());

    // Minimize chat window
    minimizeButton?.addEventListener('click', () => {
      if (chatWindow.classList.contains('minimized')) {
        chatWindow.classList.remove('minimized');
      } else {
        chatWindow.classList.add('minimized');
      }
    });

    // Send chat message
    const sendMessage = () => {
      if (chatInput.value.trim()) {
        this.sendChatMessage(chatWindow, chatInput.value.trim());
        chatInput.value = '';
      }
    };

    sendButton?.addEventListener('click', sendMessage);
    chatInput?.addEventListener('keypress', e => {
      if (e.key === 'Enter') {
        sendMessage();
      }
    });

    // Ignore analysis
    ignoreButton?.addEventListener('click', () => {
      const analysisResult = chatWindow.querySelector('.analysis-result');
      if (analysisResult) {
        analysisResult.innerHTML = `
          <div class="ignored-analysis">
            <strong>✅ Analysis Ignored</strong>
            <p>You've chosen to ignore this AI detection analysis.</p>
          </div>
        `;
      }
    });

    // Make window draggable by header
    this.makeChatWindowDraggable(chatWindow);
  }

  /**
   * Sends a chat message and displays the response
   * @param chatWindow - The chat window element
   * @param message - The user's message
   */
  private async sendChatMessage(chatWindow: HTMLElement, message: string): Promise<void> {
    const messagesContainer = chatWindow.querySelector('.chat-messages');
    const postId = chatWindow.getAttribute('data-post-id') || '';
    const postContent = chatWindow.getAttribute('data-post-content') || '';
    const analysisData = chatWindow.getAttribute('data-analysis') || '{}';

    let previousAnalysis;
    try {
      previousAnalysis = JSON.parse(analysisData);
    } catch {
      previousAnalysis = null;
    }

    // Add user message
    const userMessageDiv = document.createElement('div');
    userMessageDiv.className = 'user-message';
    userMessageDiv.textContent = message;
    messagesContainer?.appendChild(userMessageDiv);

    // Add loading message
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'assistant-message loading';
    loadingDiv.textContent = '🤔 Thinking...';
    messagesContainer?.appendChild(loadingDiv);

    // Scroll to bottom
    messagesContainer?.scrollTo(0, messagesContainer.scrollHeight);

    try {
      // Send message to background script to handle chat API
      const response = await chrome.runtime.sendMessage({
        type: 'CHAT_REQUEST',
        postId: postId,
        message: message,
        userId: getUserIdentifier(),
        postContent: postContent,
        previousAnalysis: previousAnalysis,
      });

      // Remove loading message
      loadingDiv.remove();

      if (response.error) {
        throw new Error(response.error);
      }

      // Add assistant response
      const assistantMessageDiv = document.createElement('div');
      assistantMessageDiv.className = 'assistant-message';
      assistantMessageDiv.textContent = response.message;
      messagesContainer?.appendChild(assistantMessageDiv);

      // Add suggested questions
      if (response.suggested_questions && response.suggested_questions.length > 0) {
        const suggestionsDiv = document.createElement('div');
        suggestionsDiv.className = 'suggested-questions';
        suggestionsDiv.innerHTML = '<div class="suggestions-label">Suggested questions:</div>';

        response.suggested_questions.forEach((question: string) => {
          const questionButton = document.createElement('button');
          questionButton.className = 'suggested-question';
          questionButton.textContent = question;
          questionButton.addEventListener('click', () => {
            const chatInput = chatWindow.querySelector('.chat-input') as HTMLInputElement;
            if (chatInput) {
              chatInput.value = question;
              chatInput.focus();
            }
          });
          suggestionsDiv.appendChild(questionButton);
        });

        messagesContainer?.appendChild(suggestionsDiv);
      }
    } catch (error) {
      console.error('Chat request failed:', error);
      loadingDiv.textContent = '❌ Sorry, I encountered an error. Please try again.';
      loadingDiv.classList.remove('loading');
    }

    // Scroll to bottom
    messagesContainer?.scrollTo(0, messagesContainer.scrollHeight);
  }

  /**
   * Loads and displays previous chat history for a post
   * @param chatWindow - The chat window element
   * @param postId - The Facebook post ID
   */
  private async loadChatHistory(chatWindow: HTMLElement, postId: string): Promise<void> {
    const messagesContainer = chatWindow.querySelector('.chat-messages');
    if (!messagesContainer) return;

    try {
      const userId = getUserIdentifier();
      console.log(`[AI-Slop] Loading chat history for post ${postId}, user ${userId}`);

      // Delegate network call to background for consistent CORS/timeout handling
      const historyData = await new Promise<ChatHistoryResponse>((resolve, reject) => {
        chrome.runtime.sendMessage(
          {
            type: 'CHAT_HISTORY_REQUEST',
            postId: postId,
            userId: userId,
          },
          response => {
            if (chrome.runtime.lastError) {
              return reject(chrome.runtime.lastError);
            }
            if (response && response.error) {
              return reject(new Error(response.error));
            }
            resolve(response);
          }
        );
      });
      console.log(`[AI-Slop] Loaded ${historyData.total_messages} previous messages`);

      // Clear existing messages (except loading indicators)
      const existingMessages = messagesContainer.querySelectorAll('.message-bubble');
      existingMessages.forEach(msg => msg.remove());

      // Add each previous message
      historyData.messages.forEach((message: ChatMessage) => {
        const messageElement = document.createElement('div');
        messageElement.className = `message-bubble ${message.role === 'user' ? 'user-message' : 'bot-message'}`;

        if (message.role === 'user') {
          messageElement.innerHTML = `
            <div class="message-content">
              <strong>You:</strong> ${this.escapeHtml(message.message)}
            </div>
            <div class="message-time">${new Date(message.created_at).toLocaleTimeString()}</div>
          `;
        } else {
          messageElement.innerHTML = `
            <div class="message-content">
              <strong>AI:</strong> ${this.escapeHtml(message.message)}
            </div>
            <div class="message-time">${new Date(message.created_at).toLocaleTimeString()}</div>
          `;
        }

        messagesContainer.appendChild(messageElement);
      });

      // Scroll to bottom to show most recent messages
      messagesContainer.scrollTo(0, messagesContainer.scrollHeight);
    } catch (error) {
      console.error(`[AI-Slop] Error loading chat history:`, error);
      // Don't show error to user, just continue without history
    }
  }

  /**
   * Escapes HTML to prevent XSS attacks
   * @param text - Text to escape
   * @returns Escaped HTML string
   */
  private escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Makes the chat window draggable by its header
   * @param chatWindow - The chat window element
   */
  private makeChatWindowDraggable(chatWindow: HTMLElement): void {
    const header = chatWindow.querySelector('.chat-window-header') as HTMLElement;
    if (!header) return;

    let isDragging = false;
    let startX = 0;
    let startY = 0;
    let xOffset = 0;
    let yOffset = 0;

    // Optimize performance by using requestAnimationFrame
    let animationId: number | null = null;
    let pendingUpdate = false;

    const updatePosition = (x: number, y: number) => {
      if (!pendingUpdate) {
        pendingUpdate = true;
        animationId = requestAnimationFrame(() => {
          // Keep window within viewport bounds (simplified calculation)
          const viewportWidth = window.innerWidth;
          const viewportHeight = window.innerHeight;
          const windowWidth = chatWindow.offsetWidth;
          // eslint-disable-next-line @typescript-eslint/no-unused-vars
          const _windowHeight = chatWindow.offsetHeight;

          const minX = -windowWidth + 100; // Allow slight off-screen
          const maxX = viewportWidth - 100;
          const minY = 0;
          const maxY = viewportHeight - 50;

          const clampedX = Math.max(minX, Math.min(maxX, x));
          const clampedY = Math.max(minY, Math.min(maxY, y));

          // Use translate3d for better performance (hardware acceleration)
          chatWindow.style.transform = `translate3d(${clampedX}px, ${clampedY}px, 0)`;

          xOffset = clampedX;
          yOffset = clampedY;
          pendingUpdate = false;
        });
      }
    };

    const handleMouseDown = (e: MouseEvent) => {
      // Don't drag when clicking buttons
      if (
        e.target instanceof Element &&
        (e.target.closest('.close-chat') || e.target.closest('.minimize-chat'))
      ) {
        return;
      }

      if (e.target === header || header.contains(e.target as Node)) {
        isDragging = true;
        startX = e.clientX - xOffset;
        startY = e.clientY - yOffset;

        header.style.cursor = 'grabbing';
        chatWindow.style.userSelect = 'none'; // Prevent text selection during drag

        // Add class for potential drag-specific styles
        chatWindow.classList.add('dragging');

        e.preventDefault(); // Prevent default browser drag behavior
      }
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;

      e.preventDefault();
      e.stopPropagation();

      const currentX = e.clientX - startX;
      const currentY = e.clientY - startY;

      updatePosition(currentX, currentY);
    };

    const handleMouseUp = () => {
      if (isDragging) {
        isDragging = false;
        header.style.cursor = 'grab';
        chatWindow.style.userSelect = '';
        chatWindow.classList.remove('dragging');

        // Cancel any pending animation frame
        if (animationId) {
          cancelAnimationFrame(animationId);
          animationId = null;
          pendingUpdate = false;
        }
      }
    };

    // Use passive listeners where possible for better performance
    header.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('mousemove', handleMouseMove, { passive: false });
    document.addEventListener('mouseup', handleMouseUp);

    // Handle mouse leave to stop dragging if mouse leaves window
    document.addEventListener('mouseleave', handleMouseUp);

    // Set initial cursor style
    header.style.cursor = 'grab';

    // Clean up function (store reference if needed later)
    (chatWindow as HTMLElement & { _dragCleanup?: () => void })._dragCleanup = () => {
      header.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('mouseleave', handleMouseUp);
      if (animationId) {
        cancelAnimationFrame(animationId);
      }
    };
  }
}

/**
 * Manages the floating Messenger-style chat window on Facebook pages
 * - Creates and controls the floating chat window
 * - Handles minimize/maximize functionality
 * - Provides Facebook Messenger-like experience
 */
class FloatingChatWindow {
  /** Chat window container */
  private chatWindow: HTMLDivElement | null = null;

  /** Minimized chat container */
  private minimizedChat: HTMLDivElement | null = null;

  /** Current state of the chat window */
  private isVisible: boolean = false;
  private isMinimized: boolean = false;

  /** Status elements */
  private statusIndicator: HTMLDivElement | null = null;
  private statusMessage: HTMLSpanElement | null = null;
  private profileStatus: HTMLParagraphElement | null = null;

  constructor() {
    this.setupMessageListener();
  }

  /**
   * Sets up message listener for extension icon clicks
   */
  private setupMessageListener(): void {
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      if (message.type === 'TOGGLE_CHAT_WINDOW') {
        this.toggleChatWindow();
        sendResponse({ success: true });
      }
    });
  }

  /**
   * Toggles the chat window visibility
   */
  private toggleChatWindow(): void {
    if (this.isVisible) {
      this.hideChatWindow();
    } else {
      this.showChatWindow();
    }
  }

  /**
   * Shows the chat window
   */
  private showChatWindow(): void {
    if (!this.chatWindow) {
      this.createChatWindow();
    }

    this.isVisible = true;

    if (this.isMinimized) {
      if (this.minimizedChat) {
        this.minimizedChat.style.display = 'block';
      }
    } else {
      if (this.chatWindow) {
        this.chatWindow.style.display = 'flex';
      }
    }
  }

  /**
   * Hides the chat window
   */
  private hideChatWindow(): void {
    this.isVisible = false;

    if (this.chatWindow) {
      this.chatWindow.style.display = 'none';
    }

    if (this.minimizedChat) {
      this.minimizedChat.style.display = 'none';
    }
  }

  /**
   * Creates the floating chat window with Messenger-style UI
   */
  private createChatWindow(): void {
    // Create messenger window
    this.chatWindow = document.createElement('div');
    this.chatWindow.className = 'ai-slop-messenger-window';
    this.chatWindow.id = 'ai-slop-messenger-window';
    this.chatWindow.innerHTML = `
      <div class="ai-slop-messenger-header">
        <div class="ai-slop-profile-info">
          <div class="ai-slop-profile-avatar">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
            </svg>
          </div>
          <div class="ai-slop-profile-details">
            <h3 class="ai-slop-profile-name">AI Slop Detector</h3>
            <p class="ai-slop-profile-status">Active <span class="ai-slop-active-time">now</span></p>
          </div>
        </div>
        <div class="ai-slop-header-actions">
          <button class="ai-slop-header-btn" id="ai-slop-call-btn" title="Call">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6.62 10.79c1.44 2.83 3.76 5.15 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z"/>
            </svg>
          </button>
          <button class="ai-slop-header-btn" id="ai-slop-video-btn" title="Video call">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"/>
            </svg>
          </button>
          <button class="ai-slop-header-btn" id="ai-slop-minimize-btn" title="Minimize">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 13H5v-2h14v2z"/>
            </svg>
          </button>
          <button class="ai-slop-header-btn ai-slop-close-btn" id="ai-slop-close-btn" title="Close">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>
      </div>

      <div class="ai-slop-messages-container">
        <div class="ai-slop-messages-list">
          <div class="ai-slop-message-group left">
            <div class="ai-slop-message-avatar">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
              </svg>
            </div>
            <div class="ai-slop-message-bubbles">
              <div class="ai-slop-message-bubble ai-slop-bot-bubble">
                Hello! I'm here to help you AI slop detection Facebook posts.
              </div>
              <div class="ai-slop-message-bubble ai-slop-bot-bubble">
                Click the eye icon on any post to verify its content 👁️
              </div>
            </div>
          </div>

          <div class="ai-slop-message-group right">
            <div class="ai-slop-message-bubbles">
              <div class="ai-slop-message-bubble ai-slop-user-bubble">
                <div class="ai-slop-status-info">
                  <div class="ai-slop-status-indicator"></div>
                  <span class="ai-slop-status-message">Ready to AI slop detection Facebook posts! 🎉</span>
                </div>
              </div>
            </div>
          </div>

          <div class="ai-slop-message-group left">
            <div class="ai-slop-message-avatar">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
              </svg>
            </div>
            <div class="ai-slop-message-bubbles">
              <div class="ai-slop-message-bubble ai-slop-bot-bubble">
                💡 <strong>Pro tip:</strong> Look for the eye icon next to post reactions for instant AI slop detection!
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="ai-slop-message-input-container">
        <div class="ai-slop-input-actions left">
          <button class="ai-slop-input-btn" title="Attach file">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z"/>
            </svg>
          </button>
          <button class="ai-slop-input-btn" title="Add photo">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/>
            </svg>
          </button>
        </div>
        <div class="ai-slop-message-input">
          <input type="text" placeholder="Type a message..." readonly>
        </div>
        <div class="ai-slop-input-actions right">
          <button class="ai-slop-input-btn ai-slop-emoji-btn" title="Add emoji">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm3.5-9c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-7 0c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5 7.67 11 8.5 11zm3.5 6.5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z"/>
            </svg>
          </button>
          <button class="ai-slop-input-btn ai-slop-like-btn" title="Send like">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-1.91l-.01-.01L23 10z"/>
            </svg>
          </button>
        </div>
      </div>
    `;

    // Create minimized chat
    this.minimizedChat = document.createElement('div');
    this.minimizedChat.className = 'ai-slop-minimized-chat';
    this.minimizedChat.id = 'ai-slop-minimized-chat';
    this.minimizedChat.style.display = 'none';
    this.minimizedChat.innerHTML = `
      <div class="ai-slop-minimized-content">
        <div class="ai-slop-minimized-avatar">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
          </svg>
        </div>
        <span class="ai-slop-minimized-name">AI Slop Detector</span>
        <button class="ai-slop-expand-btn" id="ai-slop-expand-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 8l-6 6 1.41 1.41L12 10.83l4.59 4.58L18 14z"/>
          </svg>
        </button>
      </div>
    `;

    // Add to page
    document.body.appendChild(this.chatWindow);
    document.body.appendChild(this.minimizedChat);

    // Set up event listeners
    this.setupChatEventListeners();

    // Get reference to status elements
    this.statusIndicator = this.chatWindow.querySelector('.ai-slop-status-indicator');
    this.statusMessage = this.chatWindow.querySelector('.ai-slop-status-message');
    this.profileStatus = this.chatWindow.querySelector('.ai-slop-profile-status');
  }

  /**
   * Sets up event listeners for the chat window
   */
  private setupChatEventListeners(): void {
    if (!this.chatWindow || !this.minimizedChat) return;

    // Minimize button
    const minimizeBtn = this.chatWindow.querySelector('#ai-slop-minimize-btn');
    minimizeBtn?.addEventListener('click', () => {
      this.minimizeChat();
    });

    // Expand button
    const expandBtn = this.minimizedChat.querySelector('#ai-slop-expand-btn');
    expandBtn?.addEventListener('click', () => {
      this.expandChat();
    });

    // Close button
    const closeBtn = this.chatWindow.querySelector('#ai-slop-close-btn');
    closeBtn?.addEventListener('click', () => {
      this.hideChatWindow();
    });

    // Click minimized chat to expand
    this.minimizedChat.addEventListener('click', e => {
      if (e.target !== expandBtn) {
        this.expandChat();
      }
    });

    // Decorative buttons (show coming soon message)
    const decorativeButtons = this.chatWindow.querySelectorAll(
      '#ai-slop-call-btn, #ai-slop-video-btn, .ai-slop-input-btn, .ai-slop-message-input input'
    );
    decorativeButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        this.showNotImplementedMessage();
      });
    });
  }

  /**
   * Minimizes the chat window
   */
  private minimizeChat(): void {
    this.isMinimized = true;
    if (this.chatWindow) {
      this.chatWindow.style.display = 'none';
    }
    if (this.minimizedChat) {
      this.minimizedChat.style.display = 'block';
    }
  }

  /**
   * Expands the chat window
   */
  private expandChat(): void {
    this.isMinimized = false;
    if (this.minimizedChat) {
      this.minimizedChat.style.display = 'none';
    }
    if (this.chatWindow) {
      this.chatWindow.style.display = 'flex';
    }
  }

  /**
   * Shows a temporary notification
   */
  private showNotImplementedMessage(): void {
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: #3a3a3a;
      color: white;
      padding: 12px 20px;
      border-radius: 20px;
      font-size: 14px;
      z-index: 10001;
      opacity: 0;
      transition: opacity 0.3s ease;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    `;
    notification.textContent = 'Feature coming soon!';
    document.body.appendChild(notification);

    setTimeout(() => (notification.style.opacity = '1'), 10);
    setTimeout(() => {
      notification.style.opacity = '0';
      setTimeout(() => document.body.removeChild(notification), 300);
    }, 2000);
  }
}

// Initialize both components when the content script loads
new FacebookPostObserver();
new FloatingChatWindow();
