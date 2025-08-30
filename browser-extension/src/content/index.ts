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
    // Enable Mixpanel analytics only for allowed groups
    const allowed = isInAllowedGroupNow();
    analytics.setEnabled(allowed);
    if (allowed) analytics.init();

    // Initialize metrics collection only for allowed contexts
    if (allowed) {
      await metricsManager.initialize();
    } else {
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
      window.addEventListener('locationchange', () => {
        if (isInAllowedGroupNow()) {
          metricsManager.initialize().catch(() => {});
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
