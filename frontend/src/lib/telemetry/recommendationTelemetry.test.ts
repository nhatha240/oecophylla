import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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

  afterEach(() => {
    vi.useRealTimers();
  });

  it('batches a click with its impression context and a stable tab session', async () => {
    const storage = new MemoryStorage();
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response(JSON.stringify({ accepted: 1 }), { status: 200 })
    );
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
    expect(client.detailContext(context.post_id)).toEqual(context);
    expect(client.detailContext(context.post_id)).toEqual({
      post_id: context.post_id,
      impression_id: null,
      request_id: null,
      model_version: null,
      position: null,
    });
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
      .fn<(_input: RequestInfo | URL, _init?: RequestInit) => Promise<Response>>()
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

  it('refreshes an expired access session and retries the same event batch', async () => {
    let batchAttempts = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      if (String(input) === '/api/v1/auth/refresh') return new Response('', { status: 200 });
      batchAttempts += 1;
      return new Response('', { status: batchAttempts === 1 ? 401 : 200 });
    });
    const client = new RecommendationTelemetryClient({
      fetch: fetchMock as typeof fetch,
      storage: new MemoryStorage(),
      randomUUID: vi.fn()
        .mockReturnValueOnce('21000000-0000-4000-8000-000000000001')
        .mockReturnValueOnce('21000000-0000-4000-8000-000000000002'),
    });

    client.click(context);
    await client.flush();

    expect(fetchMock.mock.calls.map(([input]) => String(input))).toEqual([
      '/api/v1/interactions/events/batch',
      '/api/v1/auth/refresh',
      '/api/v1/interactions/events/batch',
    ]);
    const first = JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body));
    const retry = JSON.parse(String((fetchMock.mock.calls[2]?.[1] as RequestInit).body));
    expect(retry.events[0].client_event_id).toBe(first.events[0].client_event_id);
  });

  it('does not reuse an impression after another account signs in in the same tab', () => {
    const storage = new MemoryStorage();
    const fetchMock = vi.fn();
    const first = new RecommendationTelemetryClient({
      fetch: fetchMock as typeof fetch,
      storage,
      viewerId: 'account-a',
      randomUUID: vi.fn()
        .mockReturnValueOnce('22000000-0000-4000-8000-000000000001')
        .mockReturnValueOnce('22000000-0000-4000-8000-000000000002'),
    });
    first.click(context);

    const second = new RecommendationTelemetryClient({
      fetch: fetchMock as typeof fetch,
      storage,
      viewerId: 'account-b',
      randomUUID: () => '22000000-0000-4000-8000-000000000003',
    });
    expect(first.detailContext(context.post_id, 'account-a')).toEqual(context);
    expect(second.detailContext(context.post_id, 'account-b')).toEqual({
      post_id: context.post_id,
      impression_id: null,
      request_id: null,
      model_version: null,
      position: null,
    });
  });

  it('sends a valid qualified detail view without an impression', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response(JSON.stringify({ accepted: 1 }), { status: 200 })
    );
    const client = new RecommendationTelemetryClient({
      fetch: fetchMock as typeof fetch,
      storage: new MemoryStorage(),
      randomUUID: vi.fn()
        .mockReturnValueOnce('30000000-0000-4000-8000-000000000001')
        .mockReturnValueOnce('30000000-0000-4000-8000-000000000002'),
      labelVersion: 'v2',
    });

    client.view({ ...context, impression_id: null, request_id: null, model_version: null, position: null }, 'detail', 10_000);
    await client.flush();

    const body = JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body));
    expect(body.events[0]).toMatchObject({
      impression_id: null,
      event_version: 'v2',
      event_type: 'view',
      dwell_ms: 10_000,
      metadata: { continuous_visible_ms: 10_000, trigger: 'detail' },
    });
  });

  it('persists the same measured duration for view and dwell telemetry', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response('{}', { status: 200 })
    );
    const ids = [
      '40000000-0000-4000-8000-000000000001',
      '40000000-0000-4000-8000-000000000002',
      '40000000-0000-4000-8000-000000000003',
    ];
    const client = new RecommendationTelemetryClient({
      fetch: fetchMock as typeof fetch,
      storage: new MemoryStorage(),
      randomUUID: () => ids.shift()!,
      labelVersion: 'v2',
    });

    client.view(context, 'feed', 10_000);
    client.dwell(context, 12_500, 'viewport_exit');
    await client.flush();

    const body = JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body));
    expect(body.events).toEqual([
      expect.objectContaining({ event_version: 'v2', event_type: 'view', dwell_ms: 10_000 }),
      expect.objectContaining({ event_version: 'v2', event_type: 'dwell', dwell_ms: 12_500 }),
    ]);
  });

  it('persists one visit ID on a direct detail view and its dwell', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response('{}', { status: 200 })
    );
    const client = new RecommendationTelemetryClient({
      fetch: fetchMock as typeof fetch,
      storage: new MemoryStorage(),
      randomUUID: vi.fn()
        .mockReturnValueOnce('50000000-0000-4000-8000-000000000001')
        .mockReturnValueOnce('50000000-0000-4000-8000-000000000002')
        .mockReturnValueOnce('50000000-0000-4000-8000-000000000003'),
    });
    const direct = { ...context, impression_id: null };
    const visitId = '50000000-0000-4000-8000-000000000004';

    client.view(direct, 'detail', 10_000, visitId);
    client.dwell(direct, 12_000, 'destroy', visitId);
    await client.flush();

    const body = JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body));
    expect(body.events.map((event: { metadata: Record<string, string> }) => event.metadata.visit_id))
      .toEqual([visitId, visitId]);
  });

  it('records a second direct detail view for a new visit to the same post', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response('{}', { status: 200 })
    );
    const client = new RecommendationTelemetryClient({
      fetch: fetchMock as typeof fetch,
      storage: new MemoryStorage(),
      randomUUID: vi.fn()
        .mockReturnValueOnce('60000000-0000-4000-8000-000000000001')
        .mockReturnValueOnce('60000000-0000-4000-8000-000000000002')
        .mockReturnValueOnce('60000000-0000-4000-8000-000000000003'),
    });
    const direct = { ...context, impression_id: null };

    client.view(direct, 'detail', 10_000, '60000000-0000-4000-8000-000000000011');
    client.view(direct, 'detail', 10_000, '60000000-0000-4000-8000-000000000011');
    client.view(direct, 'detail', 10_000, '60000000-0000-4000-8000-000000000012');
    await client.flush();

    const body = JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body));
    expect(body.events).toHaveLength(2);
    expect(body.events.map((event: { metadata: Record<string, string> }) => event.metadata.visit_id))
      .toEqual([
        '60000000-0000-4000-8000-000000000011',
        '60000000-0000-4000-8000-000000000012',
      ]);
  });
});
