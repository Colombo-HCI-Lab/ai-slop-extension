import { ALLOWED_GROUP_IDS } from '@/content/dom/selectors';

// Best-effort check based on URL, title, and common DOM locations
export function isInAllowedGroupNow(): boolean {
  // Must be a Facebook groups page
  if (!window.location.href.includes('/groups/')) return false;

  const idFromUrl = getCurrentGroupIdFromUrl();
  if (!idFromUrl) return false;
  return ALLOWED_GROUP_IDS.includes(idFromUrl);
}

function getCurrentGroupIdFromUrl(): string | null {
  try {
    const url = new URL(window.location.href);
    // Pattern: /groups/<id>/...
    const parts = url.pathname.split('/').filter(Boolean);
    const idx = parts.indexOf('groups');
    if (idx >= 0 && parts.length > idx + 1) {
      const candidate = parts[idx + 1];
      if (/^\d{5,}$/.test(candidate)) return candidate; // numeric group id
    }
    // Some pages may provide group_id as a query param
    const qp = url.searchParams.get('group_id');
    if (qp && /^\d{5,}$/.test(qp)) return qp;
  } catch {
    // ignore
  }
  return null;
}
