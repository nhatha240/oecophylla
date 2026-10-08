export const PREFERENCE_ACTION_EVENT = 'oec:preference-action';

const PREFERENCE_ACTION_PATH = /^\/posts\/[^/]+\/(like|save|share|comments)$/;

export function notifyPreferenceAction(path: string, method?: string): void {
  if (typeof window === 'undefined') return;
  if (method !== 'POST' && method !== 'DELETE') return;
  if (!PREFERENCE_ACTION_PATH.test(path)) return;
  window.dispatchEvent(new Event(PREFERENCE_ACTION_EVENT));
}
