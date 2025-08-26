/*
  Lightweight logging utility for the extension.
  - In development builds (__DEV__ = true), logs are enabled.
  - In production builds, logs are disabled by default to keep console clean.
  - Use createLogger(scope) to get a scoped logger like: [AI-Slop][bg/api]
*/

declare const __DEV__: boolean;

export const log = (...args: unknown[]): void => {
  if (__DEV__) console.log('[AI-Slop]', ...args);
};

export const warn = (...args: unknown[]): void => {
  if (__DEV__) console.warn('[AI-Slop]', ...args);
};

export const error = (...args: unknown[]): void => {
  if (__DEV__) console.error('[AI-Slop]', ...args);
};

export const createLogger = (scope: string) => ({
  log: (...args: unknown[]) => {
    if (__DEV__) console.log('[AI-Slop]', `[${scope}]`, ...args);
  },
  warn: (...args: unknown[]) => {
    if (__DEV__) console.warn('[AI-Slop]', `[${scope}]`, ...args);
  },
  error: (...args: unknown[]) => {
    if (__DEV__) console.error('[AI-Slop]', `[${scope}]`, ...args);
  },
});
