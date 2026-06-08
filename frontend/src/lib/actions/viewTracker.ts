/**
 * Send a single view event per post per page session once it stays >= 50%
 * visible for 800ms. Posts to `POST /api/v1/posts/{id}/view` (content-service),
 * which bumps the view counter and — when authenticated — emits a `viewed`
 * interaction onto the interactions topic. Failures are swallowed: view
 * tracking must never surface to users.
 */
export function viewTracker(node: HTMLElement, postId: string) {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let sent = false;
  const io = new IntersectionObserver(
    (entries) => {
      const visible = entries.some((e) => e.isIntersecting && e.intersectionRatio >= 0.5);
      if (visible && !sent && !timer) {
        timer = setTimeout(async () => {
          sent = true;
          try {
            await fetch(`/api/v1/posts/${postId}/view`, {
              method: 'POST',
              credentials: 'include',
              headers: { 'x-requested-with': 'oec-web' },
            });
          } catch {
            // intentionally swallow — view tracking must never surface to users
          }
        }, 800);
      }
      if (!visible && timer) {
        clearTimeout(timer);
        timer = null;
      }
    },
    { threshold: [0.5] }
  );
  io.observe(node);
  return {
    destroy() {
      if (timer) clearTimeout(timer);
      io.disconnect();
    },
  };
}
