/**
 * Send a single view event per post per page session once it stays >= 50%
 * visible for 800ms. We deliberately use a private endpoint convention
 * (`POST /api/v1/posts/{id}/view`) — when the route is wired the event will
 * land on the interactions topic; until then the failed fetch is swallowed.
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
