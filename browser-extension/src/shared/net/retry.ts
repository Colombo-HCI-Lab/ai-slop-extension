export type RetryOptions = { 
  timeoutMs?: number; 
  retries?: number; 
  backoffBaseMs?: number;
  enableUserReset?: boolean;
};

// Helper function to detect foreign key constraint errors
function isForeignKeyConstraintError(errorText: string): boolean {
  return (
    errorText.includes('violates foreign key constraint') &&
    errorText.includes('user_id_fkey')
  );
}

// Helper function to reset user data and re-initialize
async function resetUserAndRetry(): Promise<string | null> {
  try {
    const { clearUserData, clearUserIdStaleFlag } = await import('../storage');
    const { initializeUser } = await import('../../background/api');
    
    // Clear the stale user data
    clearUserData();
    
    // Re-initialize user with browser info
    const browserInfo = {
      userAgent: navigator.userAgent,
      language: navigator.language,
      platform: navigator.platform,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    };
    
    const result = await initializeUser({
      browser_info: browserInfo,
      timezone: browserInfo.timezone,
      locale: navigator.language,
    });
    
    // Store the new user ID
    localStorage.setItem('ai-slop-user-id', result.user_id);
    
    // Clear the stale flag
    clearUserIdStaleFlag();
    
    return result.user_id;
  } catch (resetError) {
    console.error('Failed to reset user:', resetError);
    return null;
  }
}

export async function fetchJsonWithRetry<T = unknown>(
  url: string,
  init: RequestInit,
  opts: RetryOptions = {}
): Promise<T> {
  const timeoutMs = opts.timeoutMs ?? 15000;
  const retries = opts.retries ?? 2;
  const backoffBaseMs = opts.backoffBaseMs ?? 300;
  const enableUserReset = opts.enableUserReset ?? false;

  let userResetAttempted = false;

  for (let attempt = 0; ; attempt++) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(url, { ...init, signal: controller.signal });
      clearTimeout(id);
      if (!res.ok) {
        const text = await res.text().catch(() => '');
        
        // Check for foreign key constraint error on analytics endpoints
        if (
          enableUserReset && 
          res.status === 500 && 
          !userResetAttempted &&
          (url.includes('/analytics/') || url.includes('/events/')) &&
          isForeignKeyConstraintError(text)
        ) {
          console.log('Foreign key constraint detected, attempting user reset...');
          userResetAttempted = true;
          
          const newUserId = await resetUserAndRetry();
          if (newUserId) {
            // Update request body for POST requests
            if (init.body) {
              try {
                const bodyObj = JSON.parse(init.body as string);
                if (bodyObj.user_id) {
                  bodyObj.user_id = newUserId;
                }
                if (bodyObj.events && Array.isArray(bodyObj.events)) {
                  bodyObj.events.forEach((event: any) => {
                    if (event.user_id) {
                      event.user_id = newUserId;
                    }
                  });
                }
                init.body = JSON.stringify(bodyObj);
                console.log('Retrying POST request with new user_id:', newUserId);
                continue; // Retry with updated user_id
              } catch (parseError) {
                console.error('Failed to update request body with new user_id:', parseError);
              }
            }
            
            // Update query parameters for GET requests
            if (url.includes('user_id=')) {
              const urlObj = new URL(url);
              urlObj.searchParams.set('user_id', newUserId);
              url = urlObj.toString();
              console.log('Retrying GET request with new user_id:', newUserId);
              continue; // Retry with updated URL
            }
          }
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
