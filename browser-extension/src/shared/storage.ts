import { STORAGE_KEYS } from './constants';

export const getUserId = (): string => {
  try {
    return localStorage.getItem(STORAGE_KEYS.userId) || '';
  } catch {
    return '';
  }
};

export const getSessionId = (): string => {
  try {
    return sessionStorage.getItem(STORAGE_KEYS.sessionId) || '';
  } catch {
    return '';
  }
};

export const clearSession = (): void => {
  try {
    sessionStorage.removeItem(STORAGE_KEYS.sessionId);
  } catch {
    // Ignore errors in environments without sessionStorage
  }
};

export const clearUserId = (): void => {
  try {
    localStorage.removeItem(STORAGE_KEYS.userId);
  } catch {
    // Ignore errors in environments without localStorage
  }
};

export const clearAllUserData = (): void => {
  clearUserId();
  clearSession();
};

export const isUserIdStale = (): boolean => {
  // Check if we have a stored flag indicating the user ID is stale
  try {
    return localStorage.getItem(STORAGE_KEYS.userIdStale) === 'true';
  } catch {
    return false;
  }
};

export const markUserIdStale = (): void => {
  try {
    localStorage.setItem(STORAGE_KEYS.userIdStale, 'true');
  } catch {
    // Ignore errors in environments without localStorage
  }
};

export const clearUserIdStaleFlag = (): void => {
  try {
    localStorage.removeItem(STORAGE_KEYS.userIdStale);
  } catch {
    // Ignore errors in environments without localStorage
  }
};

export const clearUserData = (): void => {
  clearAllUserData();
  markUserIdStale();
};
