// Shared constants used across scripts

export const STORAGE_KEYS = {
  userId: 'ai-slop-user-id', // localStorage - browser-wide, persistent
  sessionId: 'ai-slop-session-id', // sessionStorage - tab-specific, ephemeral
  debug: 'ai-slop-debug',
  userIdStale: 'ai-slop-user-id-stale',
} as const;

export const CSS_PREFIX = 'ai-slop';

/**
 * Generate tab-specific session storage key
 */
export function getTabSpecificSessionKey(tabId?: string): string {
  // Use provided tabId or generate one if not provided
  const id = tabId || `tab_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  return `${STORAGE_KEYS.sessionId}-${id}`;
}

/**
 * Get all tab-specific session keys from sessionStorage
 */
export function getAllTabSessionKeys(): string[] {
  if (typeof sessionStorage === 'undefined') return [];
  
  const keys: string[] = [];
  const prefix = STORAGE_KEYS.sessionId + '-';
  
  for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    if (key && key.startsWith(prefix)) {
      keys.push(key);
    }
  }
  
  return keys;
}

/**
 * Clean up old/orphaned tab session keys
 */
export function cleanupOrphanedTabSessions(): void {
  if (typeof sessionStorage === 'undefined') return;
  
  const tabSessionKeys = getAllTabSessionKeys();
  
  // For now, just log the cleanup - in a real implementation,
  // we'd need a way to detect which tabs are still active
  if (tabSessionKeys.length > 5) {
    console.warn(`Found ${tabSessionKeys.length} tab session keys - potential cleanup needed`);
  }
}
