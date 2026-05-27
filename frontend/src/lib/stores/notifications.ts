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

function scheduleReconnect(): void {
  if (!browser || reconnectTimer !== null) return;
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    subscribeSSE();
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
    const unavailable = error instanceof ApiException && [404, 500, 502, 503].includes(error.status);
    store.set({
      items: [],
      unread: 0,
      connected: false,
      loading: false,
      unavailable
    });
  }
}

export function subscribeSSE(): () => void {
  if (!browser || stream) return () => closeStream();

  closeStream();
  stream = new EventSource('/api/v1/notifications/stream', { withCredentials: true } as EventSourceInit);

  stream.addEventListener('open', () => {
    reconnectDelay = 1000;
    store.update((state) => ({ ...state, connected: true }));
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
    scheduleReconnect();
  });

  return () => {
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    closeStream();
    setDisconnected(get(store).unavailable);
  };
}

export async function markNotificationAsRead(id: string, fetchImpl: typeof fetch = fetch): Promise<void> {
  try {
    await markNotificationRead(fetchImpl, id);
  } catch (error) {
    if (!(error instanceof ApiException) || ![404, 500, 502, 503].includes(error.status)) {
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
    if (!(error instanceof ApiException) || ![404, 500, 502, 503].includes(error.status)) {
      throw error;
    }
  }

  store.update((state) => ({
    ...state,
    items: state.items.map((item) => ({ ...item, is_read: true })),
    unread: 0
  }));
}
