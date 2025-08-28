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

    // Initialize metrics collection first
    await metricsManager.initialize();

    // Then initialize the main functionality
    new FacebookPostObserver();
    new FloatingChatWindow();
  } catch (error) {
    console.error('Failed to initialize content script:', error);
  }
})();
