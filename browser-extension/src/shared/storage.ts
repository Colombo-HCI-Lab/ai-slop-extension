import { STORAGE_KEYS } from './constants';

export const getUserId = (): string => {
  try {
    let userId = localStorage.getItem(STORAGE_KEYS.userId);
    if (!userId) {
      userId = crypto.randomUUID();
      localStorage.setItem(STORAGE_KEYS.userId, userId);
    }
    return userId;
  } catch {
    // Fallback in environments without localStorage
    return `anon-${Math.random().toString(36).slice(2)}`;
  }
};

export const getSessionId = (): string => {
  try {
    let sessionId = sessionStorage.getItem(STORAGE_KEYS.sessionId);
    if (!sessionId) {
      sessionId = crypto.randomUUID();
      sessionStorage.setItem(STORAGE_KEYS.sessionId, sessionId);
    }
    return sessionId;
  } catch {
    // Fallback in environments without sessionStorage
    return `sess-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }
};

export const clearSession = (): void => {
  try {
    sessionStorage.removeItem(STORAGE_KEYS.sessionId);
  } catch {
    // Ignore errors in environments without sessionStorage
  }
};
