import { getMixpanelToken } from './env';
import { createLogger } from './logger';

// Lazy import type to avoid bundling issues if not installed in some environments
// eslint-disable-next-line @typescript-eslint/consistent-type-imports
type Mixpanel = typeof import('mixpanel-browser');

const logger = createLogger('analytics');

class Analytics {
  private mp: Mixpanel | null = null;
  private initialized = false;
  private pending: Array<() => void> = [];

  init(): void {
    if (this.initialized) return;
    const token = getMixpanelToken();
    if (!token) {
      logger.warn('MIXPANEL_PROJECT_TOKEN not set; analytics disabled');
      return;
    }
    try {
      // Dynamic require to keep build working if dep not installed yet
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const mixpanel: Mixpanel = require('mixpanel-browser');
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
    } catch (e) {
      logger.warn('Failed to initialize Mixpanel (module missing?)', e);
    }
  }

  identify(userId: string): void {
    const run = () => this.mp?.identify?.(userId);
    if (!this.initialized) return this.pending.push(run) as unknown as void;
    run();
  }

  registerSuper(props: Record<string, unknown>): void {
    const run = () => this.mp?.register?.(props as Record<string, string | number | boolean>);
    if (!this.initialized) return this.pending.push(run) as unknown as void;
    run();
  }

  track(event: string, props?: Record<string, unknown>): void {
    const run = () => this.mp?.track?.(event, props as Record<string, string | number | boolean | null | undefined>);
    if (!this.initialized) return this.pending.push(run) as unknown as void;
    run();
  }

  timeEvent(event: string): void {
    const run = () => this.mp?.time_event?.(event);
    if (!this.initialized) return this.pending.push(run) as unknown as void;
    run();
  }
}

export const analytics = new Analytics();
