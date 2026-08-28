import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  RecommendationTelemetryClient,
  type RecommendationContext,
} from './recommendationTelemetry';

class MemoryStorage {
  private readonly values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

const context: RecommendationContext = {
  post_id: '00000000-0000-4000-8000-000000000001',
  impression_id: '00000000-0000-4000-8000-000000000002',
  request_id: '00000000-0000-4000-8000-000000000003',
  model_version: 'heuristic-v1',
  position: 4,
};

describe('RecommendationTelemetryClient', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it('batches a click with its impression context and a stable tab session', async () => {
    const storage = new MemoryStorage();
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ accepted: 1 }), { status: 200 }));
    const ids = [
      '10000000-0000-4000-8000-000000000001',
      '10000000-0000-4000-8000-000000000002',
    ];
    const client = new RecommendationTelemetryClient({
      fetch: fetchMock as typeof fetch,
      storage,
      randomUUID: () => ids.shift()!,
      now: () => new Date('2026-08-28T02:00:00.000Z'),
    });

    client.click(context);
    await client.flush();

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const body = JSON.parse(String(init.body));
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/interactions/events/batch');
    expect(init).toMatchObject({ method: 'POST', credentials: 'include', keepalive: true });
    expect(body.events[0]).toMatchObject({
      client_event_id: '10000000-0000-4000-8000-000000000002',
      post_id: context.post_id,
      impression_id: context.impression_id,
      session_id: '10000000-0000-4000-8000-000000000001',
      event_type: 'click',
      metadata: { target: 'post_detail' },
    });
  });

  it('retries the exact same client event ID after a transport failure', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(new Response(JSON.stringify({ accepted: 1 }), { status: 200 }));
    const ids = [
      '20000000-0000-4000-8000-000000000001',
      '20000000-0000-4000-8000-000000000002',
    ];
    const client = new RecommendationTelemetryClient({
      fetch: fetchMock as typeof fetch,
      storage: new MemoryStorage(),
      randomUUID: () => ids.shift()!,
    });

    client.visible(context, 0.75);
    await client.flush();
    await client.flush();

    const first = JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body));
    const retry = JSON.parse(String((fetchMock.mock.calls[1]?.[1] as RequestInit).body));
    expect(retry.events[0].client_event_id).toBe(first.events[0].client_event_id);
  });

  it('sends a valid qualified detail view without an impression', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ accepted: 1 }), { status: 200 }));
    const client = new RecommendationTelemetryClient({
      fetch: fetchMock as typeof fetch,
      storage: new MemoryStorage(),
      randomUUID: vi.fn()
        .mockReturnValueOnce('30000000-0000-4000-8000-000000000001')
        .mockReturnValueOnce('30000000-0000-4000-8000-000000000002'),
    });

    client.view({ ...context, impression_id: null, request_id: null, model_version: null, position: null }, 'detail', 0);
    await client.flush();

    const body = JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body));
    expect(body.events[0]).toMatchObject({
      impression_id: null,
      event_type: 'view',
      dwell_ms: null,
      metadata: { continuous_visible_ms: 0, trigger: 'detail' },
    });
  });
});
