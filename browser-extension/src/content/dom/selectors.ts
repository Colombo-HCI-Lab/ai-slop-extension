// Centralized DOM selectors and allowlists for content script

export const POST_CONTENT_SELECTOR = '[data-ad-comet-preview="message"]';

// Allowed Facebook group IDs. The extension activates only for these groups.
// Checked directly from the URL (e.g., /groups/<id>/...).
export const ALLOWED_GROUP_IDS: string[] = ['1280044857038905', '1638417209555402'];
