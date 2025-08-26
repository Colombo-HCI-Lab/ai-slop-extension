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
