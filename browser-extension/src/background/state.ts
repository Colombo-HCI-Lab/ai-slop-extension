// Simple in-flight request de-duplication and hashing utilities

const inFlightAiRequests: Map<string, Promise<unknown>> = new Map();

export const getInFlight = <T>(key: string): Promise<T> | undefined =>
  inFlightAiRequests.get(key) as Promise<T> | undefined;

export const setInFlight = <T>(key: string, p: Promise<T>): void => {
  inFlightAiRequests.set(key, p);
};

export const clearInFlight = (key: string): void => {
  inFlightAiRequests.delete(key);
};

export function makePostKey(
  content: string,
  postId: string,
  imageUrls?: string[],
  videoUrls?: string[],
  postUrl?: string,
  hasVideos?: boolean
): string {
  const fingerprint = JSON.stringify({
    cl: content.length,
    c0: content.slice(0, 200),
    ic: imageUrls?.length || 0,
    vc: videoUrls?.length || 0,
    pu: (postUrl || '').slice(0, 200),
    hv: !!hasVideos,
  });
  return `${postId}|${hashString(fingerprint)}`;
}

export function hashString(input: string): string {
  let hash = 5381;
  for (let i = 0; i < input.length; i++) {
    hash = (hash * 33) ^ input.charCodeAt(i);
  }
  return (hash >>> 0).toString(16);
}
