import { browser } from '$app/environment';
import { get, writable } from 'svelte/store';
import { ApiException } from '$lib/api';
import {
  getNotificationUnreadCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead
} from '$lib/api/notifications';
import type { Notification } from '$lib/types';

type NotificationsState = {
  items: Notification[];
  unread: number;
  connected: boolean;
  loading: boolean;
  unavailable: boolean;
};

const store = writable<NotificationsState>({
  items: [],
  unread: 0,
  connected: false,
  loading: false,
  unavailable: false
});

let initialized = false;
let stream: EventSource | null = null;
let reconnectTimer: number | null = null;
let reconnectDelay = 1000;
let active = false;
let recovering = false;

function dedupe(items: Notification[]): Notification[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

function setDisconnected(unavailable = false): void {
  store.update((state) => ({ ...state, connected: false, unavailable }));
}

function isServiceUnavailable(error: unknown): boolean {
  return error instanceof ApiException && [404, 500, 502, 503].includes(error.status);
}

function clearReconnectTimer(): void {
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function scheduleReconnect(fetchImpl: typeof fetch): void {
  if (!browser || reconnectTimer !== null || !active) return;
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    void openStream(fetchImpl);
  }, reconnectDelay);
  reconnectDelay = reconnectDelay === 1000 ? 2000 : reconnectDelay === 2000 ? 5000 : 10000;
}

function closeStream(): void {
  if (stream) {
    stream.close();
    stream = null;
  }
}

export const notifications = {
  subscribe: store.subscribe
};

export async function initNotifications(fetchImpl: typeof fetch = fetch): Promise<void> {
  if (!browser || initialized) return;
  initialized = true;
  store.update((state) => ({ ...state, loading: true }));

  try {
    const [list, unread] = await Promise.all([
      listNotifications(fetchImpl, { limit: 20 }),
      getNotificationUnreadCount(fetchImpl)
    ]);
    store.set({
      items: list.items,
      unread: unread.count,
      connected: false,
      loading: false,
      unavailable: false
    });
  } catch (error) {
    const unavailable = isServiceUnavailable(error);
    store.set({
      items: [],
      unread: 0,
      connected: false,
      loading: false,
      unavailable
    });
  }
}

async function probeNotifications(fetchImpl: typeof fetch): Promise<boolean> {
  try {
    await getNotificationUnreadCount(fetchImpl);
    store.update((state) => ({ ...state, unavailable: false }));
    return true;
  } catch (error) {
    if (isServiceUnavailable(error)) {
      setDisconnected(true);
      return false;
    }

    throw error;
  }
}

async function recoverStream(fetchImpl: typeof fetch): Promise<void> {
  if (recovering || !active) return;
  recovering = true;

  try {
    const ready = await probeNotifications(fetchImpl);
    if (!active || !ready) return;
    scheduleReconnect(fetchImpl);
  } catch {
    if (!active) return;
    scheduleReconnect(fetchImpl);
  } finally {
    recovering = false;
  }
}

async function openStream(fetchImpl: typeof fetch): Promise<void> {
  if (!browser || stream || !active) return;

  closeStream();
  stream = new EventSource('/api/v1/notifications/stream', { withCredentials: true } as EventSourceInit);

  stream.addEventListener('open', () => {
    reconnectDelay = 1000;
    store.update((state) => ({ ...state, connected: true, unavailable: false }));
  });

  stream.addEventListener('heartbeat', () => {});

  stream.addEventListener('notification', (event) => {
    try {
      const item = JSON.parse((event as MessageEvent).data) as Notification;
      store.update((state) => ({
        ...state,
        items: dedupe([item, ...state.items]).slice(0, 20),
        unread: state.unread + (item.is_read ? 0 : 1)
      }));
    } catch {
      return;
    }
  });

  stream.addEventListener('error', () => {
    closeStream();
    setDisconnected(get(store).unavailable);
    void recoverStream(fetchImpl);
  });
}

function resetNotifications(): void {
  initialized = false;
  store.set({
    items: [],
    unread: 0,
    connected: false,
    loading: false,
    unavailable: false
  });
}

export function subscribeSSE(fetchImpl: typeof fetch = fetch): () => void {
  if (!browser || stream) return () => closeStream();
  active = true;

  if (!get(store).unavailable) {
    void openStream(fetchImpl);
  }

  return () => {
    active = false;
    recovering = false;
    clearReconnectTimer();
    closeStream();
    resetNotifications();
  };
}

export async function markNotificationAsRead(id: string, fetchImpl: typeof fetch = fetch): Promise<void> {
  try {
    await markNotificationRead(fetchImpl, id);
  } catch (error) {
    if (!isServiceUnavailable(error)) {
      throw error;
    }
  }

  store.update((state) => {
    const items = state.items.map((item) => (item.id === id ? { ...item, is_read: true } : item));
    const unread = items.reduce((count, item) => count + (item.is_read ? 0 : 1), 0);
    return { ...state, items, unread };
  });
}

export async function markAllNotificationsAsRead(fetchImpl: typeof fetch = fetch): Promise<void> {
  try {
    await markAllNotificationsRead(fetchImpl);
  } catch (error) {
    if (!isServiceUnavailable(error)) {
      throw error;
    }
  }

  store.update((state) => ({
    ...state,
    items: state.items.map((item) => ({ ...item, is_read: true })),
    unread: 0
  }));
}
