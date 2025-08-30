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
