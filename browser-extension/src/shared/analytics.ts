import { getMixpanelToken } from './env';
import { createLogger } from './logger';

// Lazy import type to avoid bundling issues if not installed in some environments
// eslint-disable-next-line @typescript-eslint/consistent-type-imports
type Mixpanel = typeof import('mixpanel-browser');

const logger = createLogger('analytics');

class Analytics {
  private mp: Mixpanel | null = null;
  private initialized = false;
  private enabled = false;
  private pending: Array<() => void> = [];

  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
  }

  init(): void {
    if (this.initialized || !this.enabled) return;
    const token = getMixpanelToken();
    if (!token) {
      logger.warn('MIXPANEL_PROJECT_TOKEN not set; analytics disabled');
      return;
    }
    // Dynamic import to avoid forbidden require() and to keep builds resilient
    // to the dependency being optional in some environments
    // Note: fire-and-forget; pending calls will be flushed when ready
    // eslint-disable-next-line @typescript-eslint/no-floating-promises
    import('mixpanel-browser')
      .then(mod => {
        const mixpanel: Mixpanel = (mod as unknown as { default?: Mixpanel }).default || (mod as Mixpanel);
        mixpanel.init(token, {
          debug: false,
          ignore_dnt: true,
          batch_requests: true,
        });
        this.mp = mixpanel;
        this.initialized = true;

        // Flush any queued calls
        this.pending.forEach(fn => fn());
        this.pending = [];
        logger.log('Mixpanel initialized');
      })
      .catch(e => {
        logger.warn('Failed to initialize Mixpanel (module missing?)', e);
      });
  }

  identify(userId: string): void {
    if (!this.enabled) return;
    const run = () => this.mp?.identify?.(userId);
    if (!this.initialized) return this.pending.push(run) as unknown as void;
    run();
  }

  registerSuper(props: Record<string, unknown>): void {
    if (!this.enabled) return;
    const run = () => this.mp?.register?.(props as Record<string, string | number | boolean>);
    if (!this.initialized) return this.pending.push(run) as unknown as void;
    run();
  }

  track(event: string, props?: Record<string, unknown>): void {
    if (!this.enabled) return;
    const run = () =>
      this.mp?.track?.(
        event,
        props as Record<string, string | number | boolean | null | undefined>
      );
    if (!this.initialized) return this.pending.push(run) as unknown as void;
    run();
  }

  timeEvent(event: string): void {
    if (!this.enabled) return;
    const run = () => this.mp?.time_event?.(event);
    if (!this.initialized) return this.pending.push(run) as unknown as void;
    run();
  }
}

export const analytics = new Analytics();
