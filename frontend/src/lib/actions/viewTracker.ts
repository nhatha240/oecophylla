import {
  clampMilliseconds,
  getRecommendationTelemetryClient,
  type RecommendationContext,
  type TelemetryRecorder,
} from '$lib/telemetry/recommendationTelemetry';
import { QUALIFIED_READ_MS } from '$lib/telemetry/recommendationLabel';

const VISIBLE_THRESHOLD_MS = 800;

interface ViewTrackerOptions {
  context: RecommendationContext;
  enabled: boolean;
  client?: TelemetryRecorder | null;
  monotonicNow?: () => number;
  qualifiedReadMs?: number;
  labelVersion?: 'v1' | 'v2';
  viewerId?: string | null;
}

export function viewTracker(node: HTMLElement, options: ViewTrackerOptions) {
  const client = options.enabled
    ? options.client ?? getRecommendationTelemetryClient(options.labelVersion, options.viewerId ?? null)
    : null;
  if (!options.enabled || !client || typeof IntersectionObserver === 'undefined') {
    return { destroy() {} };
  }

  const monotonicNow = options.monotonicNow ?? (() => performance.now());
  const qualifiedReadMs = options.qualifiedReadMs ?? QUALIFIED_READ_MS;
  let visibleTimer: ReturnType<typeof setTimeout> | null = null;
  let viewTimer: ReturnType<typeof setTimeout> | null = null;
  let visibleStartedAt: number | null = null;
  let latestRatio = 0.5;
  let intersectsAtThreshold = false;
  let visibleSent = false;
  let viewSent = false;

  function pageIsVisible(): boolean {
    return typeof document === 'undefined' || document.visibilityState === 'visible';
  }

  function clearThresholdTimers(): void {
    if (visibleTimer) clearTimeout(visibleTimer);
    if (viewTimer) clearTimeout(viewTimer);
    visibleTimer = null;
    viewTimer = null;
  }

  function finishVisibleSegment(trigger: 'viewport_exit' | 'page_hidden' | 'destroy'): void {
    if (visibleStartedAt === null) return;
    const dwellMs = clampMilliseconds(monotonicNow() - visibleStartedAt);
    visibleStartedAt = null;
    clearThresholdTimers();
    if (dwellMs > 0) client?.dwell(options.context, dwellMs, trigger);
  }

  function startVisibleSegment(): void {
    if (!intersectsAtThreshold || !pageIsVisible() || visibleStartedAt !== null) return;
    visibleStartedAt = monotonicNow();
    if (!visibleSent) {
      visibleTimer = setTimeout(() => {
        if (!pageIsVisible()) {
          finishVisibleSegment('page_hidden');
          return;
        }
        if (visibleStartedAt === null) return;
        visibleSent = true;
        visibleTimer = null;
        client?.visible(options.context, latestRatio);
      }, VISIBLE_THRESHOLD_MS);
    }
    if (!viewSent) {
      viewTimer = setTimeout(() => {
        if (!pageIsVisible()) {
          finishVisibleSegment('page_hidden');
          return;
        }
        if (visibleStartedAt === null) return;
        viewSent = true;
        viewTimer = null;
        client?.view(options.context, 'feed', qualifiedReadMs);
      }, qualifiedReadMs);
    }
  }

  const io = new IntersectionObserver(
    (entries) => {
      const visibleEntry = entries.find((entry) => entry.isIntersecting && entry.intersectionRatio >= 0.5);
      if (visibleEntry) {
        latestRatio = visibleEntry.intersectionRatio;
        intersectsAtThreshold = true;
        startVisibleSegment();
      } else {
        intersectsAtThreshold = false;
        finishVisibleSegment('viewport_exit');
      }
    },
    { threshold: [0, 0.5] }
  );

  function handleVisibilityChange(): void {
    if (pageIsVisible()) {
      startVisibleSegment();
    } else {
      finishVisibleSegment('page_hidden');
      void client?.flush();
    }
  }

  io.observe(node);
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', handleVisibilityChange);
  }

  return {
    destroy() {
      finishVisibleSegment('destroy');
      clearThresholdTimers();
      io.disconnect();
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', handleVisibilityChange);
      }
      void client.flush();
    },
  };
}
