import { describe, it, expect } from 'vitest';

function applyOptimistic(state: { liked: boolean, count: number }, ok: boolean) {
  // Initial flip
  const flipped = { liked: !state.liked, count: state.count + (state.liked ? -1 : 1) };
  // Rollback on failure
  return ok ? flipped : state;
}

describe('PostActionBar optimistic toggle', () => {
  it('flips state and counter on success', () => {
    expect(applyOptimistic({ liked: false, count: 5 }, true)).toEqual({ liked: true, count: 6 });
    expect(applyOptimistic({ liked: true,  count: 6 }, true)).toEqual({ liked: false, count: 5 });
  });
  it('rolls back on failure', () => {
    expect(applyOptimistic({ liked: false, count: 5 }, false)).toEqual({ liked: false, count: 5 });
  });
});
