import {
  clampMilliseconds,
  getRecommendationTelemetryClient,
  type RecommendationContext,
  type TelemetryRecorder,
} from '$lib/telemetry/recommendationTelemetry';

const VISIBLE_THRESHOLD_MS = 800;
const QUALIFIED_VIEW_MS = 5_000;

interface ViewTrackerOptions {
  context: RecommendationContext;
  enabled: boolean;
  client?: TelemetryRecorder | null;
  monotonicNow?: () => number;
}

export function viewTracker(node: HTMLElement, options: ViewTrackerOptions) {
  const client = options.client ?? getRecommendationTelemetryClient();
  if (!options.enabled || !client || typeof IntersectionObserver === 'undefined') {
    return { destroy() {} };
  }

  const monotonicNow = options.monotonicNow ?? (() => performance.now());
  let visibleTimer: ReturnType<typeof setTimeout> | null = null;
  let viewTimer: ReturnType<typeof setTimeout> | null = null;
  let visibleStartedAt: number | null = null;
  let latestRatio = 0.5;
  let visibleSent = false;
  let viewSent = false;

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

  const io = new IntersectionObserver(
    (entries) => {
      const visibleEntry = entries.find((entry) => entry.isIntersecting && entry.intersectionRatio >= 0.5);
      if (visibleEntry) {
        latestRatio = visibleEntry.intersectionRatio;
        if (visibleStartedAt !== null) return;
        visibleStartedAt = monotonicNow();
        if (!visibleSent) {
          visibleTimer = setTimeout(() => {
            visibleSent = true;
            visibleTimer = null;
            client.visible(options.context, latestRatio);
          }, VISIBLE_THRESHOLD_MS);
        }
        if (!viewSent) {
          viewTimer = setTimeout(() => {
            viewSent = true;
            viewTimer = null;
            client.view(options.context, 'feed', QUALIFIED_VIEW_MS);
          }, QUALIFIED_VIEW_MS);
        }
      } else {
        finishVisibleSegment('viewport_exit');
      }
    },
    { threshold: [0, 0.5] }
  );

  function handleVisibilityChange(): void {
    if (document.visibilityState !== 'hidden') return;
    finishVisibleSegment('page_hidden');
    void client?.flush();
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
