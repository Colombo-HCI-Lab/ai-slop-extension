import '../styles/content.css';

/**
 * Observes and processes Facebook posts to add fact-checking functionality
 * - Monitors DOM for new posts
 * - Injects fact-check icons into posts
 * - Handles fact-checking requests and result display
 */
export class FacebookPostObserver {
  /** MutationObserver instance for monitoring DOM changes */
  private observer: MutationObserver;

  /** Set to track processed posts and prevent duplicate processing */
  private processedPosts: Set<string>;

  /** Selector for extracting post content */
  private readonly POST_CONTENT_SELECTOR = '[data-ad-comet-preview="message"]';

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
      console.group('[FactCheck] ✅ POST DETECTED!');
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

  constructor() {
    console.group('[FactCheck] 🚀 Initializing Facebook Post Observer');
    console.log('📅 Timestamp:', new Date().toISOString());
    console.log('🌐 URL:', window.location.href);
    console.log('🏷️ Page title:', document.title);

    this.processedPosts = new Set();
    this.boundHandleScroll = this.handleScroll.bind(this);
    this.observer = new MutationObserver(this.handleMutations.bind(this));

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

    // Process any existing posts
    this.processExistingPosts().catch(error => {
      console.error('[FactCheck] Error processing existing posts:', error);
    });
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
      console.debug('[FactCheck] Processing posts after scroll');
      this.processExistingPosts().catch(error => {
        console.error('[FactCheck] Error processing posts after scroll:', error);
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
            console.error('[FactCheck] Error processing node:', error);
          });
        }
      });
    });
  }

  /**
   * Processes any posts that exist when the observer starts
   * Ensures posts loaded before observer initialization are processed
   * Updated to handle both article elements and group posts
   */
  private async processExistingPosts(): Promise<void> {
    let validPostsFound = 0;

    // Query articles (regular feed posts)
    const articlePosts = document.querySelectorAll('[role="article"]');
    for (const element of articlePosts) {
      if (element instanceof HTMLElement && this.isFacebookPost(element)) {
        validPostsFound++;
        await this.processPost(element);
      }
    }

    // For Facebook groups, also check for div elements with specific patterns
    // Look for containers with author headings and interaction buttons
    const groupPostCandidates = document.querySelectorAll('div');
    let groupPostsScanned = 0;

    for (const element of groupPostCandidates) {
      if (
        element instanceof HTMLElement &&
        element.querySelector('h2, h3, h4') && // Has author heading
        element.querySelectorAll('button').length > 3 && // Has multiple buttons (likely interactions)
        !element.closest('[role="article"]')
      ) {
        // Not already inside an article

        groupPostsScanned++;
        if (this.isFacebookPost(element)) {
          validPostsFound++;
          await this.processPost(element);
        }
      }
    }

    // Only log if we found valid posts or scanned group posts
    if (validPostsFound > 0 || groupPostsScanned > 0) {
      console.log('[FactCheck] 📈 Scan complete:', {
        totalArticles: articlePosts.length,
        groupPostsScanned: groupPostsScanned,
        validPosts: validPostsFound,
        totalProcessed: this.processedPosts.size,
      });
    }
  }

  /**
   * Processes a DOM node to find and handle Facebook posts
   * Updated to handle both articles and group post structures
   * @param node - HTML element to process
   */
  private async processNode(node: HTMLElement): Promise<void> {
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
   * Adds fact-checking functionality if not already processed
   * @param postElement - The post's HTML element
   */
  private async processPost(postElement: HTMLElement): Promise<void> {
    // Generate unique ID for the post
    const postId = await this.generatePostId(postElement);

    if (this.processedPosts.has(postId)) {
      // Check if icon still exists
      const existingIcon = postElement.querySelector('.fact-check-icon');
      if (existingIcon) {
        console.debug(`[FactCheck] ⏭️ Post ${postId} already processed and icon exists, skipping`);
        return;
      } else {
        console.log(`[FactCheck] 🔄 Post ${postId} was processed but icon missing, re-injecting`);
        // Remove from processed set to allow re-injection
        this.processedPosts.delete(postId);
      }
    }

    // Also check if the post already has a fact-check icon
    if (postElement.querySelector('.fact-check-icon')) {
      console.debug(`[FactCheck] ⏭️ Post already has icon, adding to processed set`);
      this.processedPosts.add(postId);
      return;
    }

    this.processedPosts.add(postId);
    console.log(`[FactCheck] 🔄 Processing new post ${postId}:`, this.processedPosts.size);

    // Extract and log post content immediately for debugging
    await this.extractPostContent(postElement);

    this.injectFactCheckIcon(postElement, postId);
  }

  /**
   * Generates a unique ID for a post based on its content and DOM characteristics
   * @param postElement - The post's HTML element
   * @returns Base64 encoded string combining multiple unique characteristics
   */
  private async generatePostId(postElement: HTMLElement): Promise<string> {
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
      content.length > 200 && content.toLowerCase().includes('facebook'.repeat(10));

    let uniqueString: string;

    if (isGenericContent || content.length < 20) {
      // Use DOM-based identification for posts with poor content extraction
      uniqueString = `${authorText}-${timeText}-${timeHref}-${position}-${postElement.className}-${Date.now()}`;
      console.log(`[FactCheck] 🆔 Using DOM-based ID for post with generic content`);
    } else {
      // Use content-based identification for posts with good content
      uniqueString = `${content.slice(0, 100)}-${authorText}`;
    }

    try {
      return btoa(encodeURIComponent(uniqueString));
    } catch (error) {
      // Ultimate fallback
      const fallbackId = `${Date.now()}-${Math.random()}-${position}`;
      console.warn(`[FactCheck] ⚠️ Using fallback ID generation:`, error);
      return btoa(fallbackId);
    }
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

    // 3. For group posts, try to find text content that's not in headers or buttons
    if (!content.trim()) {
      // Clone the element to avoid modifying the original
      const clone = postElement.cloneNode(true) as HTMLElement;

      // Remove elements that shouldn't be part of the post content
      const elementsToRemove = clone.querySelectorAll(
        [
          'h1',
          'h2',
          'h3',
          'h4',
          'h5',
          'h6', // Headers (author names, etc.)
          'button', // Interaction buttons
          'nav',
          '[role="button"]', // Navigation and button roles
          '[aria-label*="Like"]',
          '[aria-label*="Comment"]',
          '[aria-label*="Share"]', // Interaction elements
          'img',
          'svg', // Images and icons
          'time', // Timestamps
          'a[href*="/user/"]', // User profile links
          '[data-testid]', // Facebook test IDs
          '.timestamp', // Timestamp classes (if any)
        ].join(', ')
      );

      elementsToRemove.forEach(el => el.remove());

      // Get the remaining text content
      content = clone.textContent || '';
      extractionMethod = 'Fallback text extraction';
    }

    // 4. Final fallback: get all text content and filter out common non-content patterns
    if (!content.trim()) {
      const allText = postElement.textContent || '';
      // Filter out common patterns that aren't post content
      const filteredText = allText
        .replace(/\b(Like|Comment|Share|React)\b/gi, '') // Remove interaction words
        .replace(/\d+\s*(likes?|comments?|shares?)/gi, '') // Remove count text
        .replace(/\b\d+[a-z]\b/gi, '') // Remove timestamps like "3w", "2h"
        .replace(/Moderator|Author/gi, '') // Remove role indicators
        .trim();

      if (filteredText.length > 20) {
        content = filteredText;
        extractionMethod = 'Text filtering fallback';
      }
    }

    // Clean up the content
    content = content.trim().replace(/\s+/g, ' ');

    // Log extraction results
    console.log('[FactCheck] 📄 Content extracted:', {
      method: extractionMethod,
      length: content.length,
      preview: content.substring(0, 150) + (content.length > 150 ? '...' : ''),
    });

    if (content.length === 0) {
      console.warn('[FactCheck] ⚠️ No content extracted from post!');
    }

    return content;
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
        console.debug('[FactCheck] 📄 No "See more" button found in post');
        break;
      }

      console.log('[FactCheck] 🔍 Found "See more" button, expanding content...');

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
          console.log('[FactCheck] ✅ Content expanded successfully', {
            beforeLength: beforeContent,
            afterLength: afterContent,
            expanded: afterContent - beforeContent,
          });

          // Wait a bit more for any additional content loading
          await new Promise(resolve => setTimeout(resolve, 200));
          break;
        } else {
          console.log('[FactCheck] ⚠️ Content expansion may not have worked, retrying...');
          attempts++;
        }
      } catch (error) {
        console.warn('[FactCheck] ⚠️ Error clicking "See more" button:', error);
        attempts++;
      }
    }

    if (attempts >= maxAttempts) {
      console.log('[FactCheck] ⏹️ Reached maximum expansion attempts');
    }
  }

  /**
   * Injects the fact-check icon into a Facebook post
   * Creates and adds the interactive icon element with enhanced targeting
   * @param postElement - The post's HTML element
   * @param postId - Unique identifier for the post used for logging and debugging
   */
  private injectFactCheckIcon(postElement: HTMLElement, postId: string): void {
    console.log(`[FactCheck] 🎯 Starting icon injection for post: ${postId}`);
    const iconContainer = document.createElement('div');
    iconContainer.className = 'fact-check-icon';
    iconContainer.setAttribute('data-post-id', postId); // Store postId for tracking
    iconContainer.innerHTML = `
      <svg viewBox="0 0 24 24" width="20" height="20">
        <path fill="#1877f2" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm0-14c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm0 10c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4z"/>
      </svg>
    `;

    // Add click handler
    iconContainer.addEventListener('click', () => this.handleFactCheck(postElement, postId));

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
      const existingIcon = postElement.querySelector('.fact-check-icon');
      if (existingIcon) {
        console.warn(`[FactCheck] ⚠️ Icon already exists for post ${postId}, skipping injection`);
        return;
      }

      console.log(`[FactCheck] 🎯 Target element found via: ${injectionMethod}`, targetElement);

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
        console.log(`[FactCheck] 📍 Set target element position to relative`);
      }

      try {
        targetElement.appendChild(iconContainer);
        console.log(
          `[FactCheck] ✅ Icon injected successfully for post ${postId} via ${injectionMethod}`
        );
      } catch (error) {
        console.error(`[FactCheck] ❌ Failed to append icon for post ${postId}:`, error);
      }
    } else {
      console.error(
        `[FactCheck] ❌ Failed to find suitable element for icon injection for post ${postId}`
      );

      // Add debug information about the post structure
      console.log(`[FactCheck] 🔍 Post element structure for debugging:`, {
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
   * Handles the fact-check process when icon is clicked
   * Sends content to background script and displays results
   * @param postElement - The post's HTML element
   * @param postId - Unique identifier for the post used for logging and debugging
   */
  private async handleFactCheck(postElement: HTMLElement, postId: string): Promise<void> {
    const content = await this.extractPostContent(postElement);

    // Show loading state
    this.updateIconState(postElement, 'loading');

    try {
      const response = await chrome.runtime.sendMessage({
        type: 'FACT_CHECK_REQUEST',
        content: content,
        postId: postId, // Include postId for tracking
      });

      if (response.error) {
        throw new Error(response.error);
      }

      this.showFactCheckResult(postElement, response);
    } catch (error) {
      console.error(`Fact check failed for post ${postId}:`, error);
      this.updateIconState(postElement, 'error');
    }
  }

  /**
   * Updates the fact-check icon's visual state
   * @param postElement - The post's HTML element
   * @param state - Current state of the fact-check process
   */
  private updateIconState(postElement: HTMLElement, state: 'loading' | 'error'): void {
    const icon = postElement.querySelector('.fact-check-icon');
    if (icon) {
      icon.setAttribute('data-state', state);
    }
  }

  /**
   * Displays fact-check results in an overlay
   * Creates and shows an overlay with verdict, confidence, and explanation
   */
  private showFactCheckResult(
    postElement: HTMLElement,
    result: {
      verdict: string;
      confidence: number;
      explanation: string;
    }
  ): void {
    const overlay = document.createElement('div');
    overlay.className = 'fact-check-overlay';
    overlay.innerHTML = `
      <div class="fact-check-result ${result.verdict}">
        <h3>${this.formatVerdict(result.verdict)}</h3>
        <div class="confidence">
          Confidence: ${Math.round(result.confidence * 100)}%
        </div>
        <p>${result.explanation}</p>
        <button class="close-overlay">Close</button>
      </div>
    `;

    // Add close handler
    const closeButton = overlay.querySelector('.close-overlay');
    if (closeButton) {
      closeButton.addEventListener('click', () => overlay.remove());
    }

    document.body.appendChild(overlay);
  }

  /**
   * Formats the fact-check verdict for display
   * @param verdict - Raw verdict from the fact-check API
   * @returns Human-readable verdict text
   */
  private formatVerdict(verdict: string): string {
    const verdicts: Record<string, string> = {
      misinformation: 'Misinformation Detected',
      verified: 'Information Verified',
      unknown: 'Verification Inconclusive',
    };
    return verdicts[verdict] || 'Verification Error';
  }
}

// Initialize the Facebook post observer when the content script loads
new FacebookPostObserver();
