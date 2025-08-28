// Environment helpers injected via DefinePlugin

// Note: Webpack DefinePlugin replaces the exact expression `process.env.BACKEND_URL`
// with a string literal at build time. Do not use optional chaining here or
// the replacement won't occur and `process` will be referenced at runtime.
declare const process: { env: { BACKEND_URL: string; MIXPANEL_PROJECT_TOKEN?: string } };

export const getBackendUrl = (): string => {
  // This expression is replaced by DefinePlugin; no runtime `process` access remains.
  const injected = process.env.BACKEND_URL as unknown as string;
  const url = injected || '';
  return url.replace(/\/$/, '');
};

export const getApiBase = (): string => `${getBackendUrl()}/api/v1`;

export const getMixpanelToken = (): string | undefined => {
  const token = (process.env.MIXPANEL_PROJECT_TOKEN as unknown as string) || '';
  return token || undefined;
};
