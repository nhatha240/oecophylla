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
  dwell_ms: number | null;
  metadata: Record<string, string | number>;
  occurred_at: string;
}

export interface TelemetryRecorder {
  visible(context: RecommendationContext, viewportRatio: number): void;
  view(context: RecommendationContext, trigger: ViewTrigger, continuousVisibleMs: number): void;
  click(context: RecommendationContext): void;
  dwell(context: RecommendationContext, dwellMs: number, trigger: DwellTrigger): void;
  flush(): Promise<void>;
}

interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

interface TelemetryClientOptions {
  fetch: typeof fetch;
  storage: StorageLike;
  randomUUID?: () => string;
  now?: () => Date;
  flushDelayMs?: number;
}

interface StoredDetailContext {
  context: RecommendationContext;
  stored_at: number;
}

export class RecommendationTelemetryClient implements TelemetryRecorder {
  private readonly fetchImpl: typeof fetch;
  private readonly storage: StorageLike;
  private readonly randomUUID: () => string;
  private readonly now: () => Date;
  private readonly flushDelayMs: number;
  private readonly sessionId: string;
  private readonly visibleKeys = new Set<string>();
  private readonly viewKeys = new Set<string>();
  private queue: BehaviorEvent[] = [];
  private flushTimer: ReturnType<typeof setTimeout> | null = null;
  private flushInFlight: Promise<void> | null = null;

  constructor(options: TelemetryClientOptions) {
    this.fetchImpl = options.fetch;
    this.storage = options.storage;
    this.randomUUID = options.randomUUID ?? (() => crypto.randomUUID());
    this.now = options.now ?? (() => new Date());
    this.flushDelayMs = options.flushDelayMs ?? 250;
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

  view(context: RecommendationContext, trigger: ViewTrigger, continuousVisibleMs: number): void {
    const key = this.eventKey(context);
    if (this.viewKeys.has(key)) return;
    this.viewKeys.add(key);
    this.enqueue(context, 'view', null, {
      continuous_visible_ms: clampMilliseconds(continuousVisibleMs),
      trigger,
    });
  }

  click(context: RecommendationContext): void {
    this.rememberDetailContext(context);
    this.enqueue(context, 'click', null, { target: 'post_detail' });
  }

  dwell(context: RecommendationContext, dwellMs: number, trigger: DwellTrigger): void {
    this.enqueue(context, 'dwell', clampMilliseconds(dwellMs), { trigger });
  }

  detailContext(postId: string): RecommendationContext {
    const fallback: RecommendationContext = {
      post_id: postId,
      impression_id: null,
      request_id: null,
      model_version: null,
      position: null,
    };
    try {
      const raw = this.storage.getItem(`${DETAIL_CONTEXT_PREFIX}${postId}`);
      if (!raw) return fallback;
      const stored = JSON.parse(raw) as StoredDetailContext;
      if (stored.context?.post_id !== postId || this.now().getTime() - stored.stored_at > DETAIL_CONTEXT_TTL_MS) {
        return fallback;
      }
      return stored.context;
    } catch {
      return fallback;
    }
  }

  flush(): Promise<void> {
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
        const response = await this.fetchImpl('/api/v1/interactions/events/batch', {
          method: 'POST',
          credentials: 'include',
          keepalive: true,
          headers: {
            'content-type': 'application/json',
            'x-requested-with': 'oec-web',
          },
          body: JSON.stringify({ events: batch }),
        });
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
      const existing = this.storage.getItem(SESSION_KEY);
      if (existing) return existing;
      const created = this.randomUUID();
      this.storage.setItem(SESSION_KEY, created);
      return created;
    } catch {
      return this.randomUUID();
    }
  }

  private eventKey(context: RecommendationContext): string {
    return context.impression_id ?? `${context.request_id ?? 'direct'}:${context.post_id}`;
  }

  private rememberDetailContext(context: RecommendationContext): void {
    try {
      const value: StoredDetailContext = { context, stored_at: this.now().getTime() };
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
    this.queue.push({
      client_event_id: this.randomUUID(),
      post_id: context.post_id,
      impression_id: context.impression_id,
      session_id: this.sessionId,
      event_type: eventType,
      dwell_ms: dwellMs,
      metadata,
      occurred_at: this.now().toISOString(),
    });
    this.scheduleFlush(this.flushDelayMs);
  }

  private scheduleFlush(delayMs: number): void {
    if (this.flushTimer) return;
    this.flushTimer = setTimeout(() => {
      this.flushTimer = null;
      void this.flush();
    }, delayMs);
  }
}

export function clampMilliseconds(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(MAX_DWELL_MS, Math.max(0, Math.round(value)));
}

let browserClient: RecommendationTelemetryClient | null = null;

export function getRecommendationTelemetryClient(): RecommendationTelemetryClient | null {
  if (typeof window === 'undefined') return null;
  if (!browserClient) {
    browserClient = new RecommendationTelemetryClient({
      fetch: window.fetch.bind(window),
      storage: window.sessionStorage,
    });
  }
  return browserClient;
}

export function trackRecommendationClick(context: RecommendationContext): void {
  getRecommendationTelemetryClient()?.click(context);
}

export function trackRecommendationDetailView(postId: string): void {
  const client = getRecommendationTelemetryClient();
  if (!client) return;
  client.view(client.detailContext(postId), 'detail', 0);
  void client.flush();
}
