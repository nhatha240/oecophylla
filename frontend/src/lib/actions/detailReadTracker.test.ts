import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { detailReadTracker } from './detailReadTracker';
import type { RecommendationContext, TelemetryRecorder } from '../telemetry/recommendationTelemetry';

const context: RecommendationContext = {
  post_id: '00000000-0000-4000-8000-000000000011',
  impression_id: '00000000-0000-4000-8000-000000000012',
  request_id: '00000000-0000-4000-8000-000000000013',
  model_version: 'heuristic-v1',
  position: 2,
};

function recorder() {
  return {
    detailContext: vi.fn((postId: string, _viewerId: string | null) => ({ ...context, post_id: postId })),
    visible: vi.fn(),
    view: vi.fn(),
    click: vi.fn(),
    dwell: vi.fn(),
    flush: vi.fn(async () => {}),
  } satisfies TelemetryRecorder & { detailContext(postId: string, viewerId: string | null): RecommendationContext };
}

describe('detailReadTracker', () => {
  let node: HTMLElement;
  let pageVisibility: DocumentVisibilityState;
  let fakeDocument: Document;
  let fakeWindow: Window;
  let emitIntersection: (ratio: number) => void;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(0);
    pageVisibility = 'visible';
    fakeDocument = new EventTarget() as Document;
    fakeWindow = new EventTarget() as Window;
    Object.defineProperty(fakeDocument, 'visibilityState', { get: () => pageVisibility });
    vi.stubGlobal('document', fakeDocument);
    vi.stubGlobal('window', fakeWindow);
    node = {} as HTMLElement;
    class FakeIntersectionObserver {
      constructor(callback: IntersectionObserverCallback) {
        emitIntersection = (ratio: number) => callback([
          { target: node, isIntersecting: ratio > 0, intersectionRatio: ratio } as unknown as IntersectionObserverEntry,
        ], this as unknown as IntersectionObserver);
      }
      observe() {}
      disconnect() {}
    }
    vi.stubGlobal('IntersectionObserver', FakeIntersectionObserver);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('does not record an immediate or short detail view', () => {
    const client = recorder();
    const action = detailReadTracker(node, {
      postId: context.post_id,
      enabled: true,
      client,
      monotonicNow: () => Date.now(),
    });

    emitIntersection(0.1);
    vi.advanceTimersByTime(9_999);
    emitIntersection(0);

    expect(client.view).not.toHaveBeenCalled();
    expect(client.dwell).toHaveBeenCalledWith(context, 9_999, 'viewport_exit', expect.any(String));
    action.destroy();
    expect(client.dwell).toHaveBeenCalledTimes(1);
  });

  it('uses the configured qualified read threshold inclusively', () => {
    const client = recorder();
    const action = detailReadTracker(node, {
      postId: context.post_id,
      enabled: true,
      client,
      monotonicNow: () => Date.now(),
      qualifiedReadMs: 12_345,
    });

    emitIntersection(0.1);
    vi.advanceTimersByTime(12_344);
    expect(client.view).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(client.view).toHaveBeenCalledWith(context, 'detail', 12_345, expect.any(String));
    action.destroy();
  });

  it('combines short segments for dwell but requires a continuous segment for view', () => {
    const client = recorder();
    const action = detailReadTracker(node, {
      postId: context.post_id,
      enabled: true,
      client,
      monotonicNow: () => Date.now(),
    });

    emitIntersection(0.1);
    vi.advanceTimersByTime(4_000);
    emitIntersection(0);
    vi.advanceTimersByTime(20_000); // Time outside the article does not count.
    emitIntersection(0.1);
    vi.advanceTimersByTime(6_000);

    expect(client.view).not.toHaveBeenCalled();
    emitIntersection(0);
    expect(client.dwell).toHaveBeenNthCalledWith(1, context, 4_000, 'viewport_exit', expect.any(String));
    expect(client.dwell).toHaveBeenNthCalledWith(2, context, 10_000, 'viewport_exit', expect.any(String));

    emitIntersection(0.1);
    vi.advanceTimersByTime(10_000);
    expect(client.view).toHaveBeenCalledTimes(1);
    expect(client.view).toHaveBeenCalledWith(context, 'detail', 10_000, expect.any(String));
    emitIntersection(0);
    expect(client.dwell).toHaveBeenNthCalledWith(3, context, 20_000, 'viewport_exit', expect.any(String));
    action.destroy();
    expect(client.view).toHaveBeenCalledTimes(1);
    expect(client.dwell).toHaveBeenCalledTimes(3);
  });

  it('pauses while the tab is hidden and flushes reading time on pagehide', () => {
    const client = recorder();
    const action = detailReadTracker(node, {
      postId: context.post_id,
      enabled: true,
      client,
      monotonicNow: () => Date.now(),
    });

    emitIntersection(0.2);
    vi.advanceTimersByTime(3_000);
    pageVisibility = 'hidden';
    fakeDocument.dispatchEvent(new Event('visibilitychange'));
    expect(client.dwell).toHaveBeenCalledWith(context, 3_000, 'page_hidden', expect.any(String));
    expect(client.flush).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(30_000);
    expect(client.view).not.toHaveBeenCalled();
    pageVisibility = 'visible';
    fakeDocument.dispatchEvent(new Event('visibilitychange'));
    vi.advanceTimersByTime(10_000);
    expect(client.view).toHaveBeenCalledWith(context, 'detail', 10_000, expect.any(String));

    fakeWindow.dispatchEvent(new Event('pagehide'));
    expect(client.dwell).toHaveBeenLastCalledWith(context, 13_000, 'page_hidden', expect.any(String));
    expect(client.flush).toHaveBeenCalledTimes(2);
    action.destroy();
    expect(client.dwell).toHaveBeenCalledTimes(2);
  });

  it('does not emit a zero-duration detail view or dwell on immediate pagehide', () => {
    const client = recorder();
    const action = detailReadTracker(node, {
      postId: context.post_id,
      enabled: true,
      client,
      monotonicNow: () => Date.now(),
    });

    emitIntersection(0.1);
    fakeWindow.dispatchEvent(new Event('pagehide'));
    action.destroy();

    expect(client.view).not.toHaveBeenCalled();
    expect(client.dwell).not.toHaveBeenCalled();
    expect(client.flush).toHaveBeenCalled();
  });

  it('starts a new reading session when client navigation changes the post', () => {
    const client = recorder();
    const options = {
      postId: context.post_id,
      userId: '00000000-0000-4000-8000-000000000021',
      enabled: true,
      client,
      monotonicNow: () => Date.now(),
    };
    const action = detailReadTracker(node, options);
    expect(client.detailContext).toHaveBeenCalledWith(context.post_id, options.userId);

    emitIntersection(0.1);
    vi.advanceTimersByTime(2_000);
    const nextPostId = '00000000-0000-4000-8000-000000000099';
    const nextUserId = '00000000-0000-4000-8000-000000000022';
    action.update({ ...options, postId: nextPostId, userId: nextUserId });

    expect(client.dwell).toHaveBeenCalledWith(context, 2_000, 'destroy', expect.any(String));
    expect(client.detailContext).toHaveBeenCalledWith(nextPostId, nextUserId);
    emitIntersection(0.1);
    vi.advanceTimersByTime(10_000);
    expect(client.view).toHaveBeenCalledWith({ ...context, post_id: nextPostId }, 'detail', 10_000, expect.any(String));
    action.destroy();
  });

  it('uses one visit ID for a read and a new ID when the article opens again', () => {
    const client = recorder();
    const options = {
      postId: context.post_id,
      enabled: true,
      client,
      monotonicNow: () => Date.now(),
    };
    const first = detailReadTracker(node, options);
    emitIntersection(0.1);
    vi.advanceTimersByTime(10_000);
    emitIntersection(0);
    first.destroy();

    const firstVisitId = client.view.mock.calls[0]?.[3];
    expect(firstVisitId).toEqual(expect.any(String));
    expect(client.dwell.mock.calls[0]?.[3]).toBe(firstVisitId);

    const second = detailReadTracker(node, options);
    emitIntersection(0.1);
    vi.advanceTimersByTime(10_000);
    emitIntersection(0);
    second.destroy();

    const secondVisitId = client.view.mock.calls[1]?.[3];
    expect(secondVisitId).toEqual(expect.any(String));
    expect(secondVisitId).not.toBe(firstVisitId);
    expect(client.dwell.mock.calls[1]?.[3]).toBe(secondVisitId);
  });
});
