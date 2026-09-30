import { refreshSession } from '$lib/api';

const SESSION_KEY = 'oecophylla:recommendation-session-id';
const DETAIL_CONTEXT_PREFIX = 'oecophylla:recommendation-detail:';
const DETAIL_CONTEXT_TTL_MS = 30 * 60 * 1000;
const MAX_DWELL_MS = 1_800_000;
const MAX_BATCH_SIZE = 100;

export interface RecommendationContext {
  post_id: string;
  impression_id: string | null;
  request_id: string | null;
  model_version: string | null;
  position: number | null;
}

export type DwellTrigger = 'viewport_exit' | 'page_hidden' | 'destroy';
export type ViewTrigger = 'feed' | 'detail';

interface BehaviorEvent {
  client_event_id: string;
  post_id: string;
  impression_id: string | null;
  session_id: string;
  event_type: 'visible' | 'view' | 'click' | 'dwell';
  event_version: 'v1' | 'v2';
  dwell_ms: number | null;
  metadata: Record<string, string | number>;
  occurred_at: string;
}

export interface TelemetryRecorder {
  visible(context: RecommendationContext, viewportRatio: number): void;
  view(context: RecommendationContext, trigger: ViewTrigger, continuousVisibleMs: number, visitId?: string): void;
  click(context: RecommendationContext): void;
  dwell(context: RecommendationContext, dwellMs: number, trigger: DwellTrigger, visitId?: string): void;
  flush(): Promise<void>;
}

interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

interface TelemetryClientOptions {
  fetch: typeof fetch;
  storage: StorageLike;
  viewerId?: string | null;
  randomUUID?: () => string;
  now?: () => Date;
  flushDelayMs?: number;
  labelVersion?: 'v1' | 'v2';
}

interface StoredDetailContext {
  context: RecommendationContext;
  stored_at: number;
  viewer_id: string | null;
}

export class RecommendationTelemetryClient implements TelemetryRecorder {
  private readonly fetchImpl: typeof fetch;
  private readonly storage: StorageLike;
  private readonly randomUUID: () => string;
  private readonly now: () => Date;
  private readonly flushDelayMs: number;
  private readonly sessionId: string;
  private readonly labelVersion: 'v1' | 'v2';
  private readonly viewerId: string | null;
  private readonly visibleKeys = new Set<string>();
  private readonly viewKeys = new Set<string>();
  private queue: BehaviorEvent[] = [];
  private flushTimer: ReturnType<typeof setTimeout> | null = null;
  private flushInFlight: Promise<void> | null = null;
  private disposed = false;

  constructor(options: TelemetryClientOptions) {
    this.fetchImpl = options.fetch;
    this.storage = options.storage;
    this.randomUUID = options.randomUUID ?? (() => crypto.randomUUID());
    this.now = options.now ?? (() => new Date());
    this.flushDelayMs = options.flushDelayMs ?? 250;
    this.labelVersion = options.labelVersion ?? 'v1';
    this.viewerId = options.viewerId ?? null;
    this.sessionId = this.loadSessionId();
  }

  visible(context: RecommendationContext, viewportRatio: number): void {
    const key = this.eventKey(context);
    if (this.visibleKeys.has(key)) return;
    this.visibleKeys.add(key);
    this.enqueue(context, 'visible', null, {
      viewport_ratio: Math.min(1, Math.max(0.5, viewportRatio)),
    });
  }

  view(context: RecommendationContext, trigger: ViewTrigger, continuousVisibleMs: number, visitId?: string): void {
    const key = this.eventKey(context, visitId);
    if (this.viewKeys.has(key)) return;
    this.viewKeys.add(key);
    const durationMs = clampMilliseconds(continuousVisibleMs);
    this.enqueue(context, 'view', durationMs, {
      continuous_visible_ms: durationMs,
      trigger,
      ...(visitId ? { visit_id: visitId } : {}),
    });
  }

  click(context: RecommendationContext): void {
    if (this.disposed) return;
    this.rememberDetailContext(context);
    this.enqueue(context, 'click', null, { target: 'post_detail' });
  }

  dwell(context: RecommendationContext, dwellMs: number, trigger: DwellTrigger, visitId?: string): void {
    this.enqueue(context, 'dwell', clampMilliseconds(dwellMs), {
      trigger,
      ...(visitId ? { visit_id: visitId } : {}),
    });
  }

  detailContext(postId: string, viewerId: string | null = this.viewerId): RecommendationContext {
    const fallback: RecommendationContext = {
      post_id: postId,
      impression_id: null,
      request_id: null,
      model_version: null,
      position: null,
    };
    try {
      const key = `${DETAIL_CONTEXT_PREFIX}${postId}`;
      const raw = this.storage.getItem(key);
      if (!raw) return fallback;
      const stored = JSON.parse(raw) as StoredDetailContext;
      if (
        stored.context?.post_id !== postId ||
        stored.viewer_id !== viewerId ||
        viewerId !== this.viewerId ||
        this.now().getTime() - stored.stored_at > DETAIL_CONTEXT_TTL_MS
      ) {
        return fallback;
      }
      // Attribution belongs to the navigation opened by this click. A later
      // direct visit to the same post must not reuse the old impression.
      this.storage.setItem(key, '');
      return stored.context;
    } catch {
      return fallback;
    }
  }

  flush(): Promise<void> {
    if (this.disposed) return Promise.resolve();
    if (this.flushTimer) {
      clearTimeout(this.flushTimer);
      this.flushTimer = null;
    }
    if (this.flushInFlight) return this.flushInFlight;
    if (this.queue.length === 0) return Promise.resolve();

    const batch = this.queue.slice(0, MAX_BATCH_SIZE);
    const batchIds = new Set(batch.map((event) => event.client_event_id));
    this.flushInFlight = (async () => {
      try {
        const sendBatch = () => this.fetchImpl('/api/v1/interactions/events/batch', {
          method: 'POST',
          credentials: 'include',
          keepalive: true,
          headers: {
            'content-type': 'application/json',
            'x-requested-with': 'oec-web',
          },
          body: JSON.stringify({ events: batch }),
        });
        let response = await sendBatch();
        if (response.status === 401 && await refreshSession(this.fetchImpl)) {
          response = await sendBatch();
        }
        if (!response.ok && (response.status === 429 || response.status >= 500)) {
          throw new Error(`telemetry_http_${response.status}`);
        }
        // Validation/auth failures are permanent for this batch. Drop them to
        // avoid a background retry loop while keeping the UI fail-silent.
        this.queue = this.queue.filter((event) => !batchIds.has(event.client_event_id));
        if (this.queue.length > 0) this.scheduleFlush(0);
      } catch {
        // Keep the same queued event objects so retries retain client_event_id.
        this.scheduleFlush(1_000);
      }
    })().finally(() => {
      this.flushInFlight = null;
    });
    return this.flushInFlight;
  }

  private loadSessionId(): string {
    try {
      const key = this.viewerId ? `${SESSION_KEY}:${this.viewerId}` : SESSION_KEY;
      const existing = this.storage.getItem(key);
      if (existing) return existing;
      const created = this.randomUUID();
      this.storage.setItem(key, created);
      return created;
    } catch {
      return this.randomUUID();
    }
  }

  private eventKey(context: RecommendationContext, visitId?: string): string {
    return context.impression_id ?? (visitId
      ? `visit:${visitId}`
      : `${context.request_id ?? 'direct'}:${context.post_id}`);
  }

  private rememberDetailContext(context: RecommendationContext): void {
    try {
      const value: StoredDetailContext = {
        context,
        stored_at: this.now().getTime(),
        viewer_id: this.viewerId,
      };
      this.storage.setItem(`${DETAIL_CONTEXT_PREFIX}${context.post_id}`, JSON.stringify(value));
    } catch {
      // sessionStorage can be unavailable in privacy modes; telemetry remains fail-silent.
    }
  }

  private enqueue(
    context: RecommendationContext,
    eventType: BehaviorEvent['event_type'],
    dwellMs: number | null,
    metadata: BehaviorEvent['metadata'],
  ): void {
    if (this.disposed) return;
    this.queue.push({
      client_event_id: this.randomUUID(),
      post_id: context.post_id,
      impression_id: context.impression_id,
      session_id: this.sessionId,
      event_type: eventType,
      event_version: this.labelVersion,
      dwell_ms: dwellMs,
      metadata,
      occurred_at: this.now().toISOString(),
    });
    this.scheduleFlush(this.flushDelayMs);
  }

  private scheduleFlush(delayMs: number): void {
    if (this.disposed) return;
    if (this.flushTimer) return;
    this.flushTimer = setTimeout(() => {
      this.flushTimer = null;
      void this.flush();
    }, delayMs);
  }

  discardPending(): void {
    this.disposed = true;
    if (this.flushTimer) clearTimeout(this.flushTimer);
    this.flushTimer = null;
    this.queue = [];
  }
}

export function clampMilliseconds(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(MAX_DWELL_MS, Math.max(0, Math.round(value)));
}

let browserClient: RecommendationTelemetryClient | null = null;
let browserViewerId: string | null = null;
let browserLabelVersion: 'v1' | 'v2' = 'v1';

export function getRecommendationTelemetryClient(
  labelVersion: 'v1' | 'v2' = 'v1',
  viewerId: string | null = null,
): RecommendationTelemetryClient | null {
  if (typeof window === 'undefined') return null;
  if (browserClient && (browserViewerId !== viewerId || browserLabelVersion !== labelVersion)) {
    browserClient.discardPending();
    browserClient = null;
  }
  if (!browserClient) {
    try {
      browserClient = new RecommendationTelemetryClient({
        fetch: window.fetch.bind(window),
        storage: window.sessionStorage,
        labelVersion,
        viewerId,
      });
      browserViewerId = viewerId;
      browserLabelVersion = labelVersion;
    } catch {
      // Storage can be blocked by browser privacy settings. Keep the UI usable.
      return null;
    }
  }
  return browserClient;
}

export function trackRecommendationClick(
  context: RecommendationContext,
  labelVersion: 'v1' | 'v2' = 'v1',
  viewerId: string | null = null,
): void {
  const client = getRecommendationTelemetryClient(labelVersion, viewerId);
  if (!client) return;
  client.click(context);
  // Start the keepalive request before navigation can unload the feed page.
  void client.flush();
}
