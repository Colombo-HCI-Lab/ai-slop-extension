import './popup.css';

/**
 * Manages the extension's popup interface
 * - Controls status indicator display
 * - Handles Facebook page detection
 * - Updates UI based on extension state
 */
class PopupManager {
  /** DOM element for visual status indicator */
  private statusIndicator: HTMLDivElement | null;

  /** DOM element for status message text */
  private statusText: HTMLParagraphElement | null;

  constructor() {
    this.statusIndicator = document.querySelector('.status-indicator');
    this.statusText = document.querySelector('.status-text');
    this.initialize();
  }

  /**
   * Initializes the popup interface
   * Sets up initial state and event listeners
   */
  private initialize(): void {
    this.checkExtensionStatus();
    this.setupEventListeners();
  }

  /**
   * Checks if the current tab is Facebook
   * Updates status indicator accordingly
   */
  private checkExtensionStatus(): void {
    // Query the active tab to check if we're on Facebook
    chrome.tabs.query(
      {
        active: true,
        currentWindow: true,
      },
      tabs => {
        const currentTab = tabs[0];
        const url = currentTab.url || '';

        if (url.includes('facebook.com')) {
          this.updateStatus('active');
        } else {
          this.updateStatus('inactive');
        }
      }
    );
  }

  /**
   * Updates the popup's visual status
   * @param status - Current extension state ('active' on Facebook, 'inactive' otherwise)
   */
  private updateStatus(status: 'active' | 'inactive'): void {
    if (this.statusIndicator && this.statusText) {
      if (status === 'active') {
        this.statusIndicator.style.backgroundColor = 'var(--success-color)';
        this.statusText.textContent = 'Ready to fact-check';
      } else {
        this.statusIndicator.style.backgroundColor = 'var(--secondary-color)';
        this.statusText.textContent = 'Navigate to Facebook to start fact-checking';
      }
    }
  }

  /**
   * Sets up message listeners for status updates
   * Handles communication with content script
   */
  private setupEventListeners(): void {
    // Listen for messages from content script
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      if (message.type === 'STATUS_UPDATE') {
        this.updateStatus(message.status);
      }
      sendResponse({ received: true });
    });
  }
}

// Create popup manager instance when DOM content is loaded
document.addEventListener('DOMContentLoaded', () => {
  new PopupManager();
});
