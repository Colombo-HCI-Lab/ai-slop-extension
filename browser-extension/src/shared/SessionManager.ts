/**
 * SessionManager - Centralized user and session management service
 * Implements singleton pattern for tab isolation and strict initialization blocking
 */

import { STORAGE_KEYS } from './constants';
import { log, error } from './logger';
import type { UserSessionInfo } from '../content/utils/initialization';

export interface SessionManagerConfig {
  requireValidSession: boolean;
  enableLogging: boolean;
}

export interface UserSessionData {
  userId: string;
  sessionId: string;
  isNewUser: boolean;
  isNewSession: boolean;
  startTime: number;
  lastActivity: number;
}

/**
 * Centralized session management with strict initialization blocking
 */
export class SessionManager {
  private static instance: SessionManager | null = null;
  private static tabId: string | null = null;

  private userSession: UserSessionData | null = null;
  private isInitialized: boolean = false;
  private initializationPromise: Promise<UserSessionData> | null = null;
  private config: SessionManagerConfig;

  private constructor(config: SessionManagerConfig = { requireValidSession: true, enableLogging: true }) {
    this.config = config;
    this.setupTabIdentifier();
    this.setupLifecycleHandlers();
    
    if (this.config.enableLogging) {
      log('SessionManager instance created', { tabId: SessionManager.tabId });
    }
  }

  /**
   * Get singleton instance for current tab
   */
  static getInstance(config?: SessionManagerConfig): SessionManager {
    if (!SessionManager.instance) {
      SessionManager.instance = new SessionManager(config);
    }
    return SessionManager.instance;
  }

  /**
   * Get unique tab identifier for session isolation
   */
  static getTabId(): string {
    if (!SessionManager.tabId) {
      SessionManager.tabId = `tab_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    return SessionManager.tabId;
  }

  /**
   * Main initialization method - blocks until user/session are valid
   * This MUST be called before any other extension activities
   */
  async initializeUserSession(): Promise<UserSessionData> {
    if (this.isInitialized && this.userSession) {
      return this.userSession;
    }

    // If initialization is already in progress, wait for it
    if (this.initializationPromise) {
      return this.initializationPromise;
    }

    this.initializationPromise = this.performInitialization();
    
    try {
      const session = await this.initializationPromise;
      this.userSession = session;
      this.isInitialized = true;
      
      if (this.config.enableLogging) {
        log('SessionManager initialized successfully', {
          userId: session.userId,
          sessionId: session.sessionId,
          isNewUser: session.isNewUser,
          isNewSession: session.isNewSession
        });
      }
      
      return session;
    } catch (err) {
      this.initializationPromise = null;
      error('SessionManager initialization failed', err);
      throw err;
    }
  }

  /**
   * Get current session if initialized, null otherwise
   */
  getCurrentSession(): UserSessionData | null {
    return this.isInitialized ? this.userSession : null;
  }

  /**
   * Require valid session - throws error if not initialized
   */
  requireValidSession(): UserSessionData {
    if (!this.isInitialized || !this.userSession) {
      throw new Error('Session not initialized. Call initializeUserSession() first.');
    }
    
    // Update last activity
    this.userSession.lastActivity = Date.now();
    return this.userSession;
  }

  /**
   * Check if session is initialized without throwing
   */
  isSessionReady(): boolean {
    return this.isInitialized && this.userSession !== null;
  }

  /**
   * Handle navigation to allowed group - initialize session if needed
   */
  async onNavigateToAllowedGroup(): Promise<void> {
    if (this.config.enableLogging) {
      log('Navigated to allowed group, initializing session');
    }
    
    await this.initializeUserSession();
  }

  /**
   * Handle navigation away from allowed group - clear session
   */
  onNavigateAwayFromAllowedGroup(): void {
    if (this.config.enableLogging) {
      log('Navigated away from allowed group, clearing session');
    }
    
    this.clearSession();
  }

  /**
   * Handle tab close - cleanup session
   */
  onTabClose(): void {
    if (this.config.enableLogging) {
      log('Tab closing, cleaning up session');
    }
    
    this.clearSession();
  }

  /**
   * Handle tab reload - reset session for re-initialization
   */
  onTabReload(): void {
    if (this.config.enableLogging) {
      log('Tab reloading, resetting session state');
    }
    
    this.clearSession();
  }

  /**
   * Clear session data and reset state
   */
  private clearSession(): void {
    // Clear session from sessionStorage (but preserve userId in localStorage)
    if (typeof sessionStorage !== 'undefined') {
      const sessionKey = this.getTabSpecificSessionKey();
      sessionStorage.removeItem(sessionKey);
    }
    
    this.userSession = null;
    this.isInitialized = false;
    this.initializationPromise = null;
    
    if (this.config.enableLogging) {
      log('Session cleared', { tabId: SessionManager.getTabId() });
    }
  }

  /**
   * Perform the actual user/session initialization
   */
  private async performInitialization(): Promise<UserSessionData> {
    // Import here to avoid circular dependencies
    const { verifyAndInitializeUserSession } = await import('../content/utils/initialization');
    
    const sessionInfo = await verifyAndInitializeUserSession();
    
    // Store session in tab-specific sessionStorage
    const sessionKey = this.getTabSpecificSessionKey();
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.setItem(sessionKey, sessionInfo.sessionId);
    }
    
    const sessionData: UserSessionData = {
      userId: sessionInfo.userId,
      sessionId: sessionInfo.sessionId,
      isNewUser: sessionInfo.isNewUser,
      isNewSession: sessionInfo.isNewSession,
      startTime: Date.now(),
      lastActivity: Date.now()
    };
    
    return sessionData;
  }

  /**
   * Generate tab-specific session storage key
   */
  private getTabSpecificSessionKey(): string {
    return `${STORAGE_KEYS.sessionId}-${SessionManager.getTabId()}`;
  }

  /**
   * Set up unique tab identifier
   */
  private setupTabIdentifier(): void {
    // Ensure we have a unique tab identifier
    SessionManager.getTabId();
  }

  /**
   * Set up lifecycle event handlers
   */
  private setupLifecycleHandlers(): void {
    // Handle page unload (tab close)
    if (typeof window !== 'undefined') {
      window.addEventListener('beforeunload', () => {
        this.onTabClose();
      });

      // Handle page visibility changes
      document.addEventListener('visibilitychange', () => {
        if (!document.hidden && this.userSession) {
          this.userSession.lastActivity = Date.now();
        }
      });
    }
  }

  /**
   * Reset singleton instance (for testing)
   */
  static resetInstance(): void {
    SessionManager.instance = null;
    SessionManager.tabId = null;
  }

  /**
   * Get session duration in milliseconds
   */
  getSessionDuration(): number {
    if (!this.userSession) return 0;
    return Date.now() - this.userSession.startTime;
  }

  /**
   * Get time since last activity in milliseconds
   */
  getTimeSinceLastActivity(): number {
    if (!this.userSession) return 0;
    return Date.now() - this.userSession.lastActivity;
  }
}