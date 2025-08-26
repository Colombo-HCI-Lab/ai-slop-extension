import { setupBackgroundMessaging } from './messaging';
declare const __DEV__: boolean;
if (!__DEV__) {
  const noop = () => {};
  console.log = noop;
  console.debug = noop;
  console.warn = noop;
  console.error = noop;
}

// Minimal entry: set up messaging and action listener
setupBackgroundMessaging();
