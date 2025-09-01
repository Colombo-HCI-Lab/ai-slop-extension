import '../styles/index.scss';
import { FacebookPostObserver } from './observer';
import { FloatingChatWindow } from './ui/components/ChatWindow';
import { metricsManager } from './metrics/MetricsManager';
import { analytics } from '@/shared/analytics';
import { isInAllowedGroupNow } from '@/content/utils/group';

declare const __DEV__: boolean;
if (!__DEV__) {
  const noop = () => {};
  console.log = noop;
  console.debug = noop;
  console.warn = noop;
  console.error = noop;
}

// Entry bootstrap: initialize metrics, observer and chat UI
(async () => {
  try {
    // Check if we're in an allowed group
    const allowed = isInAllowedGroupNow();
    
    // CRITICAL: Only enable analytics and metrics AFTER user/session verification
    if (allowed) {
      // First initialize metrics manager which will verify/init user and session
      await metricsManager.initialize();
      
      // Only after successful verification, enable Mixpanel analytics
      analytics.setEnabled(true);
      analytics.init();
    } else {
      // Not in allowed group - disable analytics
      analytics.setEnabled(false);
      // Observe future SPA navigations to enter allowed context
      const wrapHistory = (method: 'pushState' | 'replaceState') => {
        type PushReplace = (data: unknown, unused: string, url?: string | URL | null) => unknown;
        const orig = history[method].bind(history) as PushReplace;
        (history as unknown as Record<string, unknown>)[method] = ((
          data: unknown,
          unused: string,
          url?: string | URL | null
        ) => {
          const ret = orig(data, unused, url);
          window.dispatchEvent(new Event('locationchange'));
          return ret as unknown as void;
        }) as History[typeof method];
      };
      wrapHistory('pushState');
      wrapHistory('replaceState');
      window.addEventListener('popstate', () => window.dispatchEvent(new Event('locationchange')));
      let chatInitialized = false;
      window.addEventListener('locationchange', async () => {
        if (isInAllowedGroupNow()) {
          // Initialize metrics manager first (verifies user/session)
          await metricsManager.initialize().catch(() => {});
          
          // Only after verification, enable analytics
          analytics.setEnabled(true);
          analytics.init();
          
          if (!chatInitialized) {
            new FloatingChatWindow();
            chatInitialized = true;
          }
        }
      });
    }

    // Then initialize the main functionality
    new FacebookPostObserver();
    if (allowed) {
      new FloatingChatWindow();
    }
  } catch (error) {
    console.error('Failed to initialize content script:', error);
  }
})();
