import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

vi.mock('$app/environment', () => ({ browser: true }));

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  readonly listeners = new Map<string, Array<(event?: Event) => void>>();

  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event?: Event) => void): void {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  close(): void {}

  emit(type: string, event?: Event): void {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }

  static reset(): void {
    FakeEventSource.instances = [];
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' }
  });
}

describe('notifications store', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.resetModules();
    FakeEventSource.reset();
    vi.stubGlobal('window', globalThis);
    vi.stubGlobal('EventSource', FakeEventSource as unknown as typeof EventSource);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('does not open SSE when notifications service is unavailable during init', async () => {
    const { initNotifications, notifications, subscribeSSE } = await import('./notifications');
    const fetchMock = vi.fn(async () => jsonResponse({ error: { code: 'NOT_FOUND' } }, 404));

    await initNotifications(fetchMock as any);
    const unsubscribe = subscribeSSE(fetchMock as any);

    expect(get(notifications).unavailable).toBe(true);
    expect(FakeEventSource.instances).toHaveLength(0);

    unsubscribe();
  });

  it('marks notifications unavailable and stops reconnecting after an SSE error when the service probe returns 404', async () => {
    const { initNotifications, notifications, subscribeSSE } = await import('./notifications');
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ items: [], next_cursor: null }))
      .mockResolvedValueOnce(jsonResponse({ count: 0 }))
      .mockResolvedValueOnce(jsonResponse({ error: { code: 'NOT_FOUND' } }, 404));

    await initNotifications(fetchMock as any);
    const unsubscribe = subscribeSSE(fetchMock as any);

    expect(FakeEventSource.instances).toHaveLength(1);

    FakeEventSource.instances[0]?.emit('error');
    await vi.runAllTimersAsync();

    expect(get(notifications).unavailable).toBe(true);
    expect(get(notifications).connected).toBe(false);
    expect(FakeEventSource.instances).toHaveLength(1);

    unsubscribe();
  });
});
