// Messenger-style floating chat window component
import { metricsManager } from '@/content/metrics/MetricsManager';

export class FloatingChatWindow {
  /** Chat window container */
  private chatWindow: HTMLDivElement | null = null;

  /** Minimized chat container */
  private minimizedChat: HTMLDivElement | null = null;

  /** Current state of the chat window */
  private isVisible: boolean = false;
  private isMinimized: boolean = false;
  private visibleStartedAt: number | null = null;

  /** Status elements */
  private statusIndicator: HTMLDivElement | null = null;
  private statusMessage: HTMLSpanElement | null = null;
  private profileStatus: HTMLParagraphElement | null = null;

  constructor() {
    this.setupMessageListener();
  }

  /** Sets up message listener for extension icon clicks */
  private setupMessageListener(): void {
    chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      if (message.type === 'TOGGLE_CHAT_WINDOW') {
        metricsManager.trackEvent({ type: 'chat_widget_toggle', category: 'chat_widget' });
        this.toggleChatWindow();
        sendResponse({ success: true });
      }
    });
  }

  /** Toggles the chat window visibility */
  private toggleChatWindow(): void {
    if (this.isVisible) {
      this.hideChatWindow();
    } else {
      this.showChatWindow();
    }
  }

  /** Shows the chat window */
  private showChatWindow(): void {
    if (!this.chatWindow) {
      this.createChatWindow();
    }

    this.isVisible = true;
    metricsManager.trackEvent({ type: 'chat_widget_show', category: 'chat_widget' });
    this.visibleStartedAt = Date.now();

    if (this.isMinimized) {
      if (this.minimizedChat) this.minimizedChat.style.display = 'block';
    } else {
      if (this.chatWindow) this.chatWindow.style.display = 'flex';
    }
  }

  /** Hides the chat window */
  private hideChatWindow(): void {
    this.isVisible = false;
    metricsManager.trackEvent({ type: 'chat_widget_hide', category: 'chat_widget' });
    if (this.visibleStartedAt) {
      const duration = Date.now() - this.visibleStartedAt;
      metricsManager.trackEvent({
        type: 'chat_widget_visible_duration',
        category: 'chat_widget',
        value: duration,
        metadata: { durationMs: duration },
      });
      this.visibleStartedAt = null;
    }
    if (this.chatWindow) this.chatWindow.style.display = 'none';
    if (this.minimizedChat) this.minimizedChat.style.display = 'none';
  }

  /** Creates the floating chat window with Messenger-style UI */
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

    // Initial status update
    if (this.statusIndicator) this.statusIndicator.classList.add('active');
  }

  /** Sets up UI event listeners for the chat window */
  private setupChatEventListeners(): void {
    if (!this.chatWindow || !this.minimizedChat) return;

    const closeBtn = this.chatWindow.querySelector('#ai-slop-close-btn');
    const minimizeBtn = this.chatWindow.querySelector('#ai-slop-minimize-btn');
    const expandBtn = this.minimizedChat.querySelector('#ai-slop-expand-btn');

    closeBtn?.addEventListener('click', () => this.hideChatWindow());
    minimizeBtn?.addEventListener('click', () => {
      metricsManager.trackEvent({ type: 'chat_widget_minimize', category: 'chat_widget' });
      this.minimizeChat();
    });
    expandBtn?.addEventListener('click', () => {
      metricsManager.trackEvent({ type: 'chat_widget_expand', category: 'chat_widget' });
      this.expandChat();
    });

    const decorativeButtons = this.chatWindow.querySelectorAll(
      '#ai-slop-call-btn, #ai-slop-video-btn, .ai-slop-input-btn, .ai-slop-message-input input'
    );
    decorativeButtons.forEach(btn => {
      btn.addEventListener('click', ev => {
        const target = ev.currentTarget as HTMLElement | null;
        metricsManager.trackEvent({
          type: 'chat_widget_button_click',
          category: 'chat_widget',
          label: target?.id || target?.getAttribute('title') || 'unknown',
        });
        this.showNotImplementedMessage();
      });
    });
  }

  /** Minimizes the chat window */
  private minimizeChat(): void {
    this.isMinimized = true;
    if (this.chatWindow) this.chatWindow.style.display = 'none';
    if (this.minimizedChat) this.minimizedChat.style.display = 'block';
    // Consider minimize as end of visible session
    if (this.visibleStartedAt) {
      const duration = Date.now() - this.visibleStartedAt;
      metricsManager.trackEvent({
        type: 'chat_widget_visible_duration',
        category: 'chat_widget',
        value: duration,
        metadata: { durationMs: duration, endedBy: 'minimize' },
      });
      this.visibleStartedAt = null;
    }
  }

  /** Expands the chat window */
  private expandChat(): void {
    this.isMinimized = false;
    if (this.minimizedChat) this.minimizedChat.style.display = 'none';
    if (this.chatWindow) this.chatWindow.style.display = 'flex';
    // Start new visible session
    this.visibleStartedAt = Date.now();
  }

  /** Shows a temporary notification */
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
