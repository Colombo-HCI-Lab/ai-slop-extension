import { getUserId } from './storage';

describe('storage.getUserId', () => {
  it('returns the saved id from localStorage', () => {
    localStorage.setItem('ai-slop-user-id', 'user-1234');
    const a = getUserId();
    const b = getUserId();
    expect(a).toBe('user-1234');
    expect(a).toBe(b);
  });
});
