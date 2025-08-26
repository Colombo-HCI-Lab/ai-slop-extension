import '../styles/index.scss';
import { FacebookPostObserver } from './observer';
import { FloatingChatWindow } from './ui/components/ChatWindow';
declare const __DEV__: boolean;
if (!__DEV__) {
  const noop = () => {};
  console.log = noop;
  console.debug = noop;
  console.warn = noop;
  console.error = noop;
}

// Entry bootstrap: initialize observer and chat UI
new FacebookPostObserver();
new FloatingChatWindow();
