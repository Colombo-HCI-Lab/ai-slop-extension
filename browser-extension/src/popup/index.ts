import './popup.css';

/** Stats data structure */
interface Stats {
  postsChecked: number;
  aiDetected: number;
  humanVerified: number;
}

/** Message types */
type PopupMessage =
  | { type: 'UPDATE_STATS'; stats: Partial<Stats> }
  | { type: 'STATUS_UPDATE'; status: 'active' | 'inactive'; text: string };

/**
 * Manages the extension's popup interface
 * - Displays extension statistics
 * - Handles settings and toggles
 * - Updates UI based on extension state
 * - Provides clean, minimalistic user experience
 */
class PopupManager {
  /** Main popup container */
  private container: HTMLDivElement | null;

  /** Status elements */
  private statusDot: HTMLSpanElement | null;
  private statusText: HTMLSpanElement | null;

  /** Stats elements */
  private postsCheckedElement: HTMLElement | null;
  private aiDetectedElement: HTMLElement | null;
  private humanVerifiedElement: HTMLElement | null;

  /** Settings elements */
  private autoCheckToggle: HTMLInputElement | null;
  private showConfidenceToggle: HTMLInputElement | null;

  /** Control buttons */
  private helpBtn: HTMLButtonElement | null;
  private settingsBtn: HTMLButtonElement | null;

  /** Extension state */
  private stats: Stats = {
    postsChecked: 0,
    aiDetected: 0,
    humanVerified: 0,
  };

  constructor() {
    this.container = document.querySelector('.popup-container');
    this.statusDot = document.querySelector('.status-dot');
    this.statusText = document.querySelector('.status-text');
    this.postsCheckedElement = document.getElementById('postsChecked');
    this.aiDetectedElement = document.getElementById('aiDetected');
    this.humanVerifiedElement = document.getElementById('humanVerified');
    this.autoCheckToggle = document.getElementById('autoCheck') as HTMLInputElement;
    this.showConfidenceToggle = document.getElementById('showConfidence') as HTMLInputElement;
    this.helpBtn = document.getElementById('helpBtn') as HTMLButtonElement;
    this.settingsBtn = document.getElementById('settingsBtn') as HTMLButtonElement;

    this.initialize();
  }

  /**
   * Initializes the popup interface
   * Sets up initial state and event listeners
   */
  private initialize(): void {
    this.setupEventListeners();
    this.loadExtensionData();
    this.checkExtensionStatus();
    this.updateUI();
  }

  /**
   * Sets up event listeners for the popup interface
   */
  private setupEventListeners(): void {
    // Settings toggles
    this.autoCheckToggle?.addEventListener('change', () => {
      this.handleAutoCheckToggle();
    });

    this.showConfidenceToggle?.addEventListener('change', () => {
      this.handleShowConfidenceToggle();
    });

    // Footer buttons
    this.helpBtn?.addEventListener('click', () => {
      this.openHelpPage();
    });

    this.settingsBtn?.addEventListener('click', () => {
      this.openSettingsPage();
    });

    // Listen for messages from content script or background script
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      this.handleMessage(message, sender, sendResponse);
    });
  }

  /**
   * Handles toggle for auto-check setting
   */
  private handleAutoCheckToggle(): void {
    const isEnabled = this.autoCheckToggle?.checked || false;
    chrome.storage.sync.set({ autoCheck: isEnabled });

    // Send message to content script to update behavior
    chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, {
          type: 'UPDATE_SETTINGS',
          autoCheck: isEnabled,
        });
      }
    });
  }

  /**
   * Handles toggle for show confidence setting
   */
  private handleShowConfidenceToggle(): void {
    const isEnabled = this.showConfidenceToggle?.checked || false;
    chrome.storage.sync.set({ showConfidence: isEnabled });

    // Send message to content script to update behavior
    chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, {
          type: 'UPDATE_SETTINGS',
          showConfidence: isEnabled,
        });
      }
    });
  }

  /**
   * Opens the help page
   */
  private openHelpPage(): void {
    chrome.tabs.create({
      url: 'https://github.com/your-repo/fact-check-extension#help',
    });
  }

  /**
   * Opens the settings page or shows inline settings
   */
  private openSettingsPage(): void {
    // For now, just show a message that settings are in the popup
    this.showToast('Settings are available right here in the popup!');
  }

  /**
   * Shows a temporary toast message
   */
  private showToast(message: string): void {
    const toast = document.createElement('div');
    toast.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: var(--primary-color);
      color: white;
      padding: 12px 16px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 500;
      z-index: 10001;
      opacity: 0;
      transform: translateX(100px);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      max-width: 300px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    `;
    toast.textContent = message;
    document.body.appendChild(toast);

    // Animate in
    setTimeout(() => {
      toast.style.opacity = '1';
      toast.style.transform = 'translateX(0)';
    }, 10);

    // Remove after 3 seconds
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100px)';
      setTimeout(() => {
        if (document.body.contains(toast)) {
          document.body.removeChild(toast);
        }
      }, 300);
    }, 3000);
  }

  /**
   * Loads extension data from storage
   */
  private async loadExtensionData(): Promise<void> {
    try {
      // Load settings
      const settings = await chrome.storage.sync.get(['autoCheck', 'showConfidence']);
      if (this.autoCheckToggle) {
        this.autoCheckToggle.checked = settings.autoCheck !== false;
      }
      if (this.showConfidenceToggle) {
        this.showConfidenceToggle.checked = settings.showConfidence !== false;
      }

      // Load statistics
      const stats = await chrome.storage.local.get(['postsChecked', 'aiDetected', 'humanVerified']);
      this.stats = {
        postsChecked: stats.postsChecked || 0,
        aiDetected: stats.aiDetected || 0,
        humanVerified: stats.humanVerified || 0,
      };
    } catch (error) {
      console.error('Failed to load extension data:', error);
    }
  }

  /**
   * Checks the current extension status
   */
  private checkExtensionStatus(): void {
    chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
      if (tabs[0]) {
        const url = tabs[0].url || '';
        const isFacebookPage = url.includes('facebook.com');

        this.updateStatus(
          isFacebookPage ? 'active' : 'inactive',
          isFacebookPage ? 'Active on Facebook' : 'Not on Facebook'
        );
      }
    });
  }

  /**
   * Updates the status indicator and text
   */
  private updateStatus(status: 'active' | 'inactive', text: string): void {
    if (this.statusDot && this.statusText) {
      this.statusDot.className = `status-dot ${status}`;
      this.statusText.textContent = text;

      if (status === 'inactive' && this.statusDot) {
        this.statusDot.style.backgroundColor = 'var(--text-muted)';
      }
    }
  }

  /**
   * Updates the UI with current data
   */
  private updateUI(): void {
    // Update statistics
    if (this.postsCheckedElement) {
      this.postsCheckedElement.textContent = this.stats.postsChecked.toString();
    }
    if (this.aiDetectedElement) {
      this.aiDetectedElement.textContent = this.stats.aiDetected.toString();
    }
    if (this.humanVerifiedElement) {
      this.humanVerifiedElement.textContent = this.stats.humanVerified.toString();
    }

    // Add animation to stats
    this.animateStats();
  }

  /**
   * Animates the statistics with a count-up effect
   */
  private animateStats(): void {
    const elements = [
      { element: this.postsCheckedElement, value: this.stats.postsChecked },
      { element: this.aiDetectedElement, value: this.stats.aiDetected },
      { element: this.humanVerifiedElement, value: this.stats.humanVerified },
    ];

    elements.forEach(({ element, value }) => {
      if (element) {
        this.animateNumber(element, value);
      }
    });
  }

  /**
   * Animates a number from 0 to target value
   */
  private animateNumber(element: HTMLElement, targetValue: number): void {
    const duration = 1000; // 1 second
    const steps = 30;
    const increment = targetValue / steps;
    let current = 0;
    let step = 0;

    const timer = setInterval(() => {
      step++;
      current = Math.min(Math.round(increment * step), targetValue);
      element.textContent = current.toString();

      if (current >= targetValue) {
        clearInterval(timer);
        element.textContent = targetValue.toString();
      }
    }, duration / steps);
  }

  /**
   * Handles messages from other parts of the extension
   */
  private handleMessage(
    message: PopupMessage,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _sender: chrome.runtime.MessageSender,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _sendResponse: (response?: unknown) => void
  ): void {
    switch (message.type) {
      case 'UPDATE_STATS':
        this.updateStats(message.stats);
        break;
      case 'STATUS_UPDATE':
        this.updateStatus(message.status, message.text);
        break;
    }
  }

  /**
   * Updates extension statistics
   */
  private updateStats(newStats: Partial<Stats>): void {
    this.stats = { ...this.stats, ...newStats };

    // Save to storage
    chrome.storage.local.set(this.stats);

    // Update UI
    this.updateUI();
  }
}

// Initialize the popup when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  new PopupManager();
});

// Export for potential testing
export { PopupManager };
