import { log } from '../logger';

export type RetryOptions = { 
  timeoutMs?: number; 
  retries?: number; 
  backoffBaseMs?: number;
};


export async function fetchJsonWithRetry<T = unknown>(
  url: string,
  init: RequestInit,
  opts: RetryOptions = {}
): Promise<T> {
  const timeoutMs = opts.timeoutMs ?? 15000;
  const retries = opts.retries ?? 2;
  const backoffBaseMs = opts.backoffBaseMs ?? 300;

  for (let attempt = 0; ; attempt++) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(url, { ...init, signal: controller.signal });
      clearTimeout(id);
      if (!res.ok) {
        const text = await res.text().catch(() => '');
        
        // Check for analytics endpoint errors - quietly ignore them
        if (url.includes('/analytics/') || url.includes('/events/')) {
          log('Analytics endpoint failed, ignoring error:', { 
            status: res.status, 
            url: url.replace(/user_id=[^&]+/, 'user_id=***'),
            error: text.substring(0, 100) 
          });
          
          // For analytics endpoints, we quietly fail instead of throwing
          // This prevents analytics failures from disrupting user experience
          return {} as T; // Return empty object to indicate silent failure
        }
        
        if (res.status >= 500 && attempt < retries) {
          const delay = backoffBaseMs * Math.pow(2, attempt);
          await new Promise(r => setTimeout(r, delay));
          continue;
        }
        throw new Error(`HTTP ${res.status}: ${text}`);
      }
      return (await res.json()) as T;
    } catch (err: any) {
      clearTimeout(id);
      if (
        (err?.name === 'AbortError' || err?.message?.includes('Failed to fetch')) &&
        attempt < retries
      ) {
        const delay = backoffBaseMs * Math.pow(2, attempt);
        await new Promise(r => setTimeout(r, delay));
        continue;
      }
      throw err;
    }
  }
}
