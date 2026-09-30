import {
  clampMilliseconds,
  getRecommendationTelemetryClient,
  type RecommendationContext,
  type TelemetryRecorder,
} from '$lib/telemetry/recommendationTelemetry';
import { QUALIFIED_READ_MS } from '$lib/telemetry/recommendationLabel';

interface DetailTelemetryRecorder extends TelemetryRecorder {
  detailContext(postId: string, viewerId: string | null): RecommendationContext;
}

interface DetailReadTrackerOptions {
  postId: string;
  userId?: string | null;
  enabled: boolean;
  labelVersion?: 'v1' | 'v2';
  client?: DetailTelemetryRecorder | null;
  monotonicNow?: () => number;
  qualifiedReadMs?: number;
  visitId?: string;
}

function startTracking(node: HTMLElement, options: DetailReadTrackerOptions) {
  const client = options.enabled
    ? (options.client ?? getRecommendationTelemetryClient(options.labelVersion, options.userId ?? null))
    : null;
  if (!client || !options.postId || typeof IntersectionObserver === 'undefined') {
    return { destroy() {} };
  }

  const context = client.detailContext(options.postId, options.userId ?? null);
  const visitId = options.visitId ?? globalThis.crypto?.randomUUID?.();
  const now = options.monotonicNow ?? (() => performance.now());
  const qualifiedReadMs = options.qualifiedReadMs ?? QUALIFIED_READ_MS;
  let intersectsViewport = false;
  let pageShown = true;
  let segmentStartedAt: number | null = null;
  let accumulatedMs = 0;
  let lastDwellMs = 0;
  let viewSent = false;
  let destroyed = false;
  let viewTimer: ReturnType<typeof setTimeout> | null = null;

  function clearViewTimer(): void {
    if (viewTimer !== null) clearTimeout(viewTimer);
    viewTimer = null;
  }

  function measuredMs(): number {
    return accumulatedMs + (segmentStartedAt === null ? 0 : Math.max(0, now() - segmentStartedAt));
  }

  function sendQualifiedView(): void {
    if (viewSent || segmentStartedAt === null) return;
    const segmentMs = Math.max(0, now() - segmentStartedAt);
    if (segmentMs < qualifiedReadMs) return;
    viewSent = true;
    client?.view(context, 'detail', clampMilliseconds(segmentMs), visitId);
    clearViewTimer();
  }

  function scheduleQualifiedView(): void {
    if (viewSent || segmentStartedAt === null) return;
    const remainingMs = Math.max(0, qualifiedReadMs - (now() - segmentStartedAt));
    viewTimer = setTimeout(() => {
      viewTimer = null;
      if (segmentStartedAt === null || document.visibilityState !== 'visible' || !pageShown) return;
      sendQualifiedView();
      if (!viewSent) scheduleQualifiedView();
    }, Math.max(1, Math.ceil(remainingMs)));
  }

  function sendDwell(trigger: 'viewport_exit' | 'page_hidden' | 'destroy'): void {
    const totalMs = clampMilliseconds(accumulatedMs);
    if (totalMs <= lastDwellMs) return;
    lastDwellMs = totalMs;
    client?.dwell(context, totalMs, trigger, visitId);
  }

  function stopReading(trigger: 'viewport_exit' | 'page_hidden' | 'destroy'): void {
    if (segmentStartedAt === null) return;
    sendQualifiedView();
    accumulatedMs = measuredMs();
    segmentStartedAt = null;
    clearViewTimer();
    sendDwell(trigger);
  }

  function syncReading(trigger: 'viewport_exit' | 'page_hidden'): void {
    const shouldRead = intersectsViewport && pageShown && document.visibilityState === 'visible';
    if (!shouldRead) {
      stopReading(trigger);
    } else if (segmentStartedAt === null) {
      segmentStartedAt = now();
      scheduleQualifiedView();
    }
  }

  const observer = new IntersectionObserver((entries) => {
    const entry = entries.find((candidate) => candidate.target === node);
    if (!entry) return;
    intersectsViewport = entry.isIntersecting && entry.intersectionRatio > 0;
    syncReading('viewport_exit');
  }, { threshold: 0 });

  function handleVisibilityChange(): void {
    syncReading('page_hidden');
    if (document.visibilityState === 'hidden') void client?.flush();
  }

  function handlePageHide(): void {
    pageShown = false;
    syncReading('page_hidden');
    void client?.flush();
  }

  function handlePageShow(): void {
    pageShown = true;
    syncReading('page_hidden');
  }

  observer.observe(node);
  document.addEventListener('visibilitychange', handleVisibilityChange);
  window.addEventListener('pagehide', handlePageHide);
  window.addEventListener('pageshow', handlePageShow);

  return {
    destroy() {
      if (destroyed) return;
      destroyed = true;
      stopReading('destroy');
      clearViewTimer();
      observer.disconnect();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('pagehide', handlePageHide);
      window.removeEventListener('pageshow', handlePageShow);
      void client.flush();
    },
  };
}

export function detailReadTracker(node: HTMLElement, options: DetailReadTrackerOptions) {
  let currentOptions = options;
  let tracking = startTracking(node, options);

  return {
    update(nextOptions: DetailReadTrackerOptions) {
      if (
        nextOptions.postId === currentOptions.postId &&
        nextOptions.userId === currentOptions.userId &&
        nextOptions.enabled === currentOptions.enabled &&
        nextOptions.labelVersion === currentOptions.labelVersion &&
        nextOptions.client === currentOptions.client &&
        nextOptions.monotonicNow === currentOptions.monotonicNow &&
        nextOptions.qualifiedReadMs === currentOptions.qualifiedReadMs
        && nextOptions.visitId === currentOptions.visitId
      ) return;
      tracking.destroy();
      currentOptions = nextOptions;
      tracking = startTracking(node, nextOptions);
    },
    destroy() {
      tracking.destroy();
    },
  };
}
