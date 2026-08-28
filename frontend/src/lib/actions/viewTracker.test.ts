import { beforeEach, describe, expect, it, vi } from 'vitest';
import { viewTracker } from './viewTracker';
import type { RecommendationContext, TelemetryRecorder } from '../telemetry/recommendationTelemetry';

const context: RecommendationContext = {
  post_id: '00000000-0000-4000-8000-000000000011',
  impression_id: '00000000-0000-4000-8000-000000000012',
  request_id: '00000000-0000-4000-8000-000000000013',
  model_version: 'heuristic-v1',
  position: 2,
};

function recorder(): TelemetryRecorder {
  return {
    visible: vi.fn(),
    view: vi.fn(),
    click: vi.fn(),
    dwell: vi.fn(),
    flush: vi.fn(async () => {}),
  };
}

describe('viewTracker', () => {
  let emitIntersection: (ratio: number) => void;

  beforeEach(() => {
    vi.useFakeTimers();
    class FakeIntersectionObserver {
      constructor(callback: IntersectionObserverCallback) {
        emitIntersection = (ratio: number) => callback([
          { isIntersecting: ratio > 0, intersectionRatio: ratio } as IntersectionObserverEntry,
        ], this as unknown as IntersectionObserver);
      }
      observe() {}
      disconnect() {}
    }
    vi.stubGlobal('IntersectionObserver', FakeIntersectionObserver);
  });

  it('does not emit visible before 800 ms', () => {
    const client = recorder();
    const action = viewTracker({} as HTMLElement, { context, client, enabled: true });

    emitIntersection(0.7);
    vi.advanceTimersByTime(799);

    expect(client.visible).not.toHaveBeenCalled();
    expect(client.view).not.toHaveBeenCalled();
    action.destroy();
  });

  it('emits visible at 800 ms but not a view before five seconds', () => {
    const client = recorder();
    const action = viewTracker({} as HTMLElement, { context, client, enabled: true });

    emitIntersection(0.75);
    vi.advanceTimersByTime(800);
    expect(client.visible).toHaveBeenCalledWith(context, 0.75);

    vi.advanceTimersByTime(4_199);
    expect(client.view).not.toHaveBeenCalled();
    action.destroy();
  });

  it('emits at most one visible and qualified view after re-entry', () => {
    const client = recorder();
    const action = viewTracker({} as HTMLElement, { context, client, enabled: true });

    emitIntersection(0.8);
    vi.advanceTimersByTime(5_000);
    emitIntersection(0);
    emitIntersection(0.9);
    vi.advanceTimersByTime(5_000);

    expect(client.visible).toHaveBeenCalledTimes(1);
    expect(client.view).toHaveBeenCalledTimes(1);
    expect(client.view).toHaveBeenCalledWith(context, 'feed', 5_000);
    action.destroy();
  });

  it('clamps dwell to 30 minutes and flushes it on destroy', () => {
    let monotonicNow = 0;
    const client = recorder();
    const action = viewTracker({} as HTMLElement, {
      context,
      client,
      enabled: true,
      monotonicNow: () => monotonicNow,
    });

    emitIntersection(0.6);
    monotonicNow = 2_400_000;
    action.destroy();

    expect(client.dwell).toHaveBeenCalledWith(context, 1_800_000, 'destroy');
    expect(client.flush).toHaveBeenCalledTimes(1);
  });
});
