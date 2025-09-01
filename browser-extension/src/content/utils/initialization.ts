/**
 * User and Session initialization with verification
 */

import { STORAGE_KEYS } from '@/shared/constants';
import { log, error } from '@/shared/logger';
import { 
  initializeUser, 
  initializeSession, 
  verifyUser, 
  verifySession 
} from '../messaging';

export interface UserSessionInfo {
  userId: string;
  sessionId: string;
  isNewUser: boolean;
  isNewSession: boolean;
}

/**
 * Verifies and initializes user and session IDs.
 * This MUST be called before any analytics or post processing.
 * 
 * Flow:
 * 1. Check for existing userId and sessionId in storage
 * 2. If both exist, verify them with backend
 * 3. If user invalid -> create new user -> create new session
 * 4. If user valid but session invalid -> create new session
 * 5. Return verified/initialized IDs
 */
export async function verifyAndInitializeUserSession(): Promise<UserSessionInfo> {
  try {
    // Get existing IDs from storage
    let userId = localStorage.getItem(STORAGE_KEYS.userId) || '';
    let sessionId = sessionStorage.getItem(STORAGE_KEYS.sessionId) || '';
    
    let isNewUser = false;
    let isNewSession = false;
    let userValid = false;
    let sessionValid = false;

    // Get browser info for initialization
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    const locale = navigator.language || 'en-US';
    const browserInfo = {
      name: 'Chrome',
      userAgent: navigator.userAgent,
      platform: navigator.platform,
      language: navigator.language,
    } as const;

    // Step 1: Verify existing user ID if present
    if (userId) {
      try {
        const userVerification = await verifyUser(userId);
        userValid = userVerification.valid;
        log('User verification result', { userId, valid: userValid });
      } catch (err) {
        error('User verification failed', err);
        userValid = false;
      }
    }

    // Step 2: Initialize new user if needed
    if (!userValid) {
      try {
        const res = await initializeUser({
          timezone: tz,
          locale: locale,
          browserInfo: browserInfo as unknown as Record<string, unknown>,
        });
        userId = res.user_id;
        localStorage.setItem(STORAGE_KEYS.userId, userId);
        isNewUser = true;
        log('New user initialized', { userId });
        
        // Clear any existing session since we have a new user
        sessionId = '';
        sessionStorage.removeItem(STORAGE_KEYS.sessionId);
      } catch (err) {
        error('Failed to initialize user', err);
        throw new Error('User initialization failed');
      }
    }

    // Step 3: Verify existing session ID if present and user is valid
    if (sessionId && !isNewUser) {
      try {
        const sessionVerification = await verifySession(sessionId, userId);
        sessionValid = sessionVerification.valid;
        log('Session verification result', { sessionId, valid: sessionValid });
      } catch (err) {
        error('Session verification failed', err);
        sessionValid = false;
      }
    }

    // Step 4: Initialize new session if needed
    if (!sessionValid) {
      try {
        const sess = await initializeSession({
          userId: userId,
          browserInfo: browserInfo as unknown as Record<string, unknown>,
          timezone: tz,
          locale: locale,
        });
        sessionId = sess.session_id;
        sessionStorage.setItem(STORAGE_KEYS.sessionId, sessionId);
        isNewSession = true;
        log('New session initialized', { sessionId });
      } catch (err) {
        error('Failed to initialize session', err);
        throw new Error('Session initialization failed');
      }
    }

    // Return verified/initialized IDs
    return {
      userId,
      sessionId,
      isNewUser,
      isNewSession,
    };
  } catch (err) {
    error('Failed to verify and initialize user session', err);
    throw err;
  }
}

/**
 * Checks if we have valid user and session IDs in storage.
 * This is a quick check without backend verification.
 */
export function hasStoredUserSession(): boolean {
  const userId = localStorage.getItem(STORAGE_KEYS.userId);
  const sessionId = sessionStorage.getItem(STORAGE_KEYS.sessionId);
  return !!(userId && sessionId);
}

/**
 * Clears stored user and session IDs.
 * Use this for logout or reset scenarios.
 */
export function clearUserSession(): void {
  localStorage.removeItem(STORAGE_KEYS.userId);
  sessionStorage.removeItem(STORAGE_KEYS.sessionId);
  log('User session cleared');
}