import { getUserId } from './storage';

describe('storage.getUserId', () => {
  it('persists and returns the same id', () => {
    const a = getUserId();
    const b = getUserId();
    expect(a).toBe(b);
    expect(a).toMatch(/^[a-z0-9-]+$/i);
  });
});
