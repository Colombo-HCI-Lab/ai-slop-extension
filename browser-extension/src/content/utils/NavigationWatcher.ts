/**
 * NavigationWatcher - Monitors URL changes and manages session lifecycle
 * Handles transitions in/out of allowed Facebook groups
 */

import { log, error } from '../../shared/logger';
import { SessionManager } from '../../shared/SessionManager';
import { ALLOWED_GROUP_IDS } from '../dom/selectors';

export interface NavigationState {
  currentUrl: string;
  currentGroupId: string | null;
  isInAllowedGroup: boolean;
  lastTransition: number;
}

export interface NavigationWatcherConfig {
  enableLogging: boolean;
  debounceMs: number;
}

/**
 * Monitors navigation events and manages session lifecycle based on URL changes
 */
export class NavigationWatcher {
  private sessionManager: SessionManager;
  private currentState: NavigationState;
  private config: NavigationWatcherConfig;
  private debounceTimer: number | null = null;
  private isDestroyed: boolean = false;

  // Event handlers - bound to preserve context
  private boundLocationChangeHandler: () => void;
  private boundPopstateHandler: () => void;

  constructor(
    sessionManager: SessionManager,
    config: NavigationWatcherConfig = { enableLogging: true, debounceMs: 100 }
  ) {
    this.sessionManager = sessionManager;
    this.config = config;
    
    // Initialize current state
    this.currentState = this.getCurrentNavigationState();
    
    // Bind event handlers
    this.boundLocationChangeHandler = this.handleLocationChange.bind(this);
    this.boundPopstateHandler = this.handleLocationChange.bind(this);
    
    this.setupNavigationListeners();
    
    if (this.config.enableLogging) {
      log('NavigationWatcher initialized', {
        currentUrl: this.currentState.currentUrl,
        groupId: this.currentState.currentGroupId,
        isInAllowedGroup: this.currentState.isInAllowedGroup
      });
    }
  }

  /**
   * Get current navigation state
   */
  getCurrentState(): NavigationState {
    return { ...this.currentState };
  }

  /**
   * Check if currently in an allowed group
   */
  isCurrentlyInAllowedGroup(): boolean {
    return this.currentState.isInAllowedGroup;
  }

  /**
   * Get current group ID if in a Facebook group
   */
  getCurrentGroupId(): string | null {
    return this.currentState.currentGroupId;
  }

  /**
   * Manually trigger navigation check (useful for testing)
   */
  checkNavigation(): void {
    this.handleLocationChange();
  }

  /**
   * Destroy the navigation watcher and clean up listeners
   */
  destroy(): void {
    this.isDestroyed = true;
    
    // Clear any pending debounce timer
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
    
    // Remove event listeners
    if (typeof window !== 'undefined') {
      window.removeEventListener('locationchange', this.boundLocationChangeHandler);
      window.removeEventListener('popstate', this.boundPopstateHandler);
    }
    
    if (this.config.enableLogging) {
      log('NavigationWatcher destroyed');
    }
  }

  /**
   * Set up navigation event listeners
   */
  private setupNavigationListeners(): void {
    if (typeof window === 'undefined') return;

    // Listen for custom locationchange events (from history API wrapping)
    window.addEventListener('locationchange', this.boundLocationChangeHandler);
    
    // Listen for browser back/forward navigation
    window.addEventListener('popstate', this.boundPopstateHandler);
    
    // Wrap history API to detect programmatic navigation
    this.wrapHistoryAPI();
  }

  /**
   * Wrap history.pushState and history.replaceState to detect SPA navigation
   */
  private wrapHistoryAPI(): void {
    if (typeof window === 'undefined' || typeof history === 'undefined') return;

    const wrapHistoryMethod = (method: 'pushState' | 'replaceState') => {
      const original = history[method].bind(history);
      
      (history as any)[method] = (
        data: any,
        unused: string,
        url?: string | URL | null
      ) => {
        const result = original(data, unused, url);
        
        // Dispatch custom event for SPA navigation detection
        window.dispatchEvent(new Event('locationchange'));
        
        return result;
      };
    };

    wrapHistoryMethod('pushState');
    wrapHistoryMethod('replaceState');
  }

  /**
   * Handle location change events with debouncing
   */
  private handleLocationChange(): void {
    if (this.isDestroyed) return;

    // Debounce rapid navigation events
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }

    this.debounceTimer = window.setTimeout(() => {
      this.processLocationChange();
      this.debounceTimer = null;
    }, this.config.debounceMs);
  }

  /**
   * Process the actual location change
   */
  private processLocationChange(): void {
    if (this.isDestroyed) return;

    const newState = this.getCurrentNavigationState();
    const previousState = this.currentState;

    // Check if there's an actual change
    if (newState.currentUrl === previousState.currentUrl) {
      return; // No change
    }

    if (this.config.enableLogging) {
      log('Navigation detected', {
        from: {
          url: previousState.currentUrl,
          groupId: previousState.currentGroupId,
          isAllowed: previousState.isInAllowedGroup
        },
        to: {
          url: newState.currentUrl,
          groupId: newState.currentGroupId,
          isAllowed: newState.isInAllowedGroup
        }
      });
    }

    // Handle session lifecycle based on group transitions
    this.handleGroupTransition(previousState, newState);

    // Update current state
    this.currentState = newState;
  }

  /**
   * Handle transitions between allowed/non-allowed groups
   */
  private async handleGroupTransition(
    previousState: NavigationState,
    newState: NavigationState
  ): Promise<void> {
    const wasInAllowedGroup = previousState.isInAllowedGroup;
    const nowInAllowedGroup = newState.isInAllowedGroup;

    try {
      if (wasInAllowedGroup && !nowInAllowedGroup) {
        // Left allowed group - clear session
        if (this.config.enableLogging) {
          log('Left allowed group, clearing session', {
            fromGroup: previousState.currentGroupId,
            toUrl: newState.currentUrl
          });
        }
        
        this.sessionManager.onNavigateAwayFromAllowedGroup();
        
      } else if (!wasInAllowedGroup && nowInAllowedGroup) {
        // Entered allowed group - initialize session
        if (this.config.enableLogging) {
          log('Entered allowed group, initializing session', {
            toGroup: newState.currentGroupId,
            fromUrl: previousState.currentUrl
          });
        }
        
        await this.sessionManager.onNavigateToAllowedGroup();
        
      } else if (wasInAllowedGroup && nowInAllowedGroup && 
                 previousState.currentGroupId !== newState.currentGroupId) {
        // Moved between different allowed groups - keep session but log transition
        if (this.config.enableLogging) {
          log('Moved between allowed groups', {
            fromGroup: previousState.currentGroupId,
            toGroup: newState.currentGroupId
          });
        }
      }
    } catch (err) {
      error('Error handling group transition', err);
    }
  }

  /**
   * Get current navigation state from URL
   */
  private getCurrentNavigationState(): NavigationState {
    const currentUrl = typeof window !== 'undefined' ? window.location.href : '';
    const currentGroupId = this.getCurrentGroupIdFromUrl();
    const isInAllowedGroup = this.isInAllowedGroup(currentGroupId);

    return {
      currentUrl,
      currentGroupId,
      isInAllowedGroup,
      lastTransition: Date.now()
    };
  }

  /**
   * Extract group ID from current URL
   */
  private getCurrentGroupIdFromUrl(): string | null {
    try {
      if (typeof window === 'undefined') return null;
      
      const url = new URL(window.location.href);
      
      // Must be a Facebook groups page
      if (!url.href.includes('/groups/')) return null;
      
      // Pattern: /groups/<id>/...
      const parts = url.pathname.split('/').filter(Boolean);
      const idx = parts.indexOf('groups');
      
      if (idx >= 0 && parts.length > idx + 1) {
        const candidate = parts[idx + 1];
        if (/^\d{5,}$/.test(candidate)) {
          return candidate; // numeric group id
        }
      }
      
      // Some pages may provide group_id as a query param
      const qp = url.searchParams.get('group_id');
      if (qp && /^\d{5,}$/.test(qp)) {
        return qp;
      }
    } catch (err) {
      if (this.config.enableLogging) {
        error('Error parsing group ID from URL', err);
      }
    }
    
    return null;
  }

  /**
   * Check if group ID is in allowed list
   */
  private isInAllowedGroup(groupId: string | null): boolean {
    if (!groupId) return false;
    return ALLOWED_GROUP_IDS.includes(groupId);
  }
}

/**
 * Convenience function to create and initialize NavigationWatcher
 */
export function createNavigationWatcher(
  sessionManager: SessionManager,
  config?: NavigationWatcherConfig
): NavigationWatcher {
  return new NavigationWatcher(sessionManager, config);
}