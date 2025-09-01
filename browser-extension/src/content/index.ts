import '../styles/index.scss';
import { FacebookPostObserver } from './observer';
import { FloatingChatWindow } from './ui/components/ChatWindow';
import { analytics } from '@/shared/analytics';
import { SessionManager } from '@/shared/SessionManager';
import { initializeGlobalGate, protectedExecute } from '@/shared/InitializationGate';
import { createNavigationWatcher } from './utils/NavigationWatcher';
import { isInAllowedGroupNow } from '@/content/utils/group';
import { log, error } from '@/shared/logger';

declare const __DEV__: boolean;
if (!__DEV__) {
  const noop = () => {};
  console.log = noop;
  console.debug = noop;
  console.warn = noop;
  console.error = noop;
}

// Global instances
let navigationWatcher: ReturnType<typeof createNavigationWatcher> | null = null;
let postObserver: FacebookPostObserver | null = null;
let chatWindow: FloatingChatWindow | null = null;

/**
 * Initialize extension functionality - only called after session validation
 */
async function initializeExtensionFeatures(): Promise<void> {
  try {
    await protectedExecute(async () => {
      log('Initializing extension features');
      
      // Create post observer (but don't start processing yet)
      postObserver = new FacebookPostObserver();
      
      // Initialize chat window with protection
      chatWindow = new FloatingChatWindow();
      
      // Enable and initialize analytics
      analytics.setEnabled(true);
      analytics.init();
      
      log('Extension features initialized successfully');
    }, 'initializeExtensionFeatures');
    
    // CRITICAL: Only start post processing AFTER session validation is complete
    if (postObserver) {
      postObserver.startObserving();
      log('Post observer started after session validation');
    }
  } catch (err) {
    error('Failed to initialize extension features', err);
    throw err;
  }
}

/**
 * Set up navigation watcher for URL monitoring
 */
function setupNavigationWatcher(sessionManager: SessionManager): void {
  if (navigationWatcher) {
    navigationWatcher.destroy();
  }
  
  navigationWatcher = createNavigationWatcher(sessionManager, {
    enableLogging: __DEV__,
    debounceMs: 100
  });
  
  log('Navigation watcher initialized');
}

/**
 * Clean up extension resources
 */
function cleanupExtension(): void {
  if (navigationWatcher) {
    navigationWatcher.destroy();
    navigationWatcher = null;
  }
  
  if (postObserver) {
    // FacebookPostObserver doesn't have destroy method yet - will add in next update
    postObserver = null;
  }
  
  if (chatWindow) {
    // FloatingChatWindow doesn't have destroy method yet - will add in next update  
    chatWindow = null;
  }
  
  analytics.setEnabled(false);
  log('Extension resources cleaned up');
}

// Main entry point with new architecture
(async () => {
  try {
    log('Content script starting with new architecture');
    
    // STEP 1: Check if we're in an allowed group
    const isInAllowedGroup = isInAllowedGroupNow();
    
    if (!isInAllowedGroup) {
      log('Not in allowed group, setting up navigation watcher only');
      
      // Create session manager and navigation watcher for monitoring
      const sessionManager = SessionManager.getInstance({ 
        requireValidSession: true, 
        enableLogging: __DEV__ 
      });
      
      setupNavigationWatcher(sessionManager);
      
      // Exit early - no extension functionality until we enter allowed group
      return;
    }
    
    log('In allowed group, initializing session and extension');
    
    // STEP 2: Initialize SessionManager
    const sessionManager = SessionManager.getInstance({ 
      requireValidSession: true, 
      enableLogging: __DEV__ 
    });
    
    // STEP 3: Initialize InitializationGate with SessionManager
    // This will block until user/session are validated
    await initializeGlobalGate(sessionManager);
    
    // STEP 4: Set up navigation watcher now that we have valid session
    setupNavigationWatcher(sessionManager);
    
    // STEP 5: Only after valid session, initialize extension functionality
    await initializeExtensionFeatures();
    
    log('Content script initialization complete');
    
  } catch (err) {
    error('Failed to initialize content script with new architecture', err);
    
    // Fallback: clean up any partial initialization
    cleanupExtension();
    
    // Still set up navigation watcher in case user navigates to allowed group later
    try {
      const fallbackSessionManager = SessionManager.getInstance({ 
        requireValidSession: false, 
        enableLogging: __DEV__ 
      });
      setupNavigationWatcher(fallbackSessionManager);
    } catch (fallbackErr) {
      error('Failed to set up fallback navigation watcher', fallbackErr);
    }
  }
})();
